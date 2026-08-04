import io
import re
import html
import asyncio
import logging
import random
import time
from pathlib import Path
from urllib.parse import quote
import openpyxl
import aiosqlite
from datetime import datetime, timedelta

from aiogram import Router, F, types
from aiogram.filters import Command, StateFilter, CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    LabeledPrice, PreCheckoutQuery, Message, InlineKeyboardMarkup, 
    InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, BufferedInputFile, CallbackQuery,
    ReplyKeyboardRemove, FSInputFile
)

from app.core.config import ADMIN_IDS, LOG_CHANNEL_ID, BOT_USERNAME
from app import database as db
from app.core.keyboards import *

logger = logging.getLogger(__name__)

router = Router()

def _log_background_task_error(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    try:
        exc = task.exception()
    except asyncio.CancelledError:
        return
    if exc is not None:
        import logging
        logging.getLogger(__name__).exception("Ошибка фоновой задачи", exc_info=exc)


def is_forwarded(message: Message) -> bool:
    return bool(
        message.forward_from 
        or message.forward_from_chat 
        or message.forward_date 
        or getattr(message, "forward_origin", None)
    )

def contains_links_or_usernames(message: Message) -> bool:
    text = message.text or message.caption or ""
    link_pattern = r"(https?://\S+|t\.me/\S+|@[a-zA-Z0-9_]{4,})"
    if re.search(link_pattern, text, re.IGNORECASE):
        return True
    entities = message.entities or message.caption_entities or []
    for entity in entities:
        if entity.type in ("text_link", "url", "mention"):
            return True
    return False

chat_timeout_tasks = {}
unread_reminder_tasks = {}
search_timeout_tasks = {}
search_card_message_ids = {}

search_game_attempts = {}
search_game_last_spin = {}


def reset_search_game(user_id: int) -> None:
    """Сбрасывает мини-игру при начале нового поиска."""
    search_game_attempts.pop(user_id, None)
    search_game_last_spin.pop(user_id, None)

pending_invoice_message_ids = {}

class Broadcast(StatesGroup):
    waiting_for_message = State()
    waiting_for_button = State()
    waiting_for_text = State()
    waiting_for_confirmation = State()

class GiftAdd(StatesGroup):
    waiting_for_name = State()

class BannedWordAdd(StatesGroup):
    waiting_for_word = State()

class GiftDeleteSelect(StatesGroup):
    selecting = State()

class UserSearch(StatesGroup):
    waiting_for_query = State()

class AdminSettings(StatesGroup):
    waiting_for_reveal_cost = State()

class UserWithdraw(StatesGroup):
    waiting_for_amount = State()

class GameSoloBet(StatesGroup):
    waiting_for_bet = State()

class GameDuelBet(StatesGroup):
    waiting_for_bet = State()



async def admin_user_card(user):
    """Компактная карточка пользователя со статистикой чата и вопросов."""
    uid = int(user[0])
    full_name = f"{user[2] or ''} {user[3] or ''}".strip() or "не указано"
    joined_raw = user[4] or "неизвестно"
    try:
        joined = datetime.fromisoformat(joined_raw).strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        joined = str(joined_raw)

    blocked = bool(user[5])
    warnings = int(user[6] or 0)
    is_vip = bool(user[17]) if len(user) > 17 else False
    vip_until = user[18] if len(user) > 18 else None
    last_activity_raw = user[20] if len(user) > 20 else None
    completed_dialogs = int(user[22] or 0) if len(user) > 22 else 0
    complaints = int(user[9] or 0)

    vip_text = "Да" if is_vip else "Нет"
    if is_vip and vip_until:
        try:
            vip_text = f"Да, до {datetime.fromisoformat(vip_until):%d.%m.%Y}"
        except (TypeError, ValueError):
            pass

    if last_activity_raw:
        try:
            dt = datetime.fromisoformat(last_activity_raw)
            now = datetime.now()
            last_activity = (
                f"Сегодня, {dt:%H:%M}" if dt.date() == now.date()
                else dt.strftime("%d.%m.%Y, %H:%M")
            )
        except (TypeError, ValueError):
            last_activity = str(last_activity_raw)
    else:
        last_activity = "неизвестно"

    async with aiosqlite.connect(db.DB_PATH, timeout=10) as connection:
        connection.row_factory = aiosqlite.Row

        async def scalar(sql: str, params=()):
            row = await (await connection.execute(sql, params)).fetchone()
            return int((row[0] if row else 0) or 0)

        last_log = await (await connection.execute(
            "SELECT action FROM logs WHERE user_id=? ORDER BY id DESC LIMIT 1", (uid,)
        )).fetchone()
        action_map = {
            "question_sent": "Отправил вопрос",
            "question_answered": "Ответил на вопрос",
            "question_reveal_sent": "Раскрыл автора вопроса",
            "question_stars_sent": "Отправил звёзды",
            "question_gift_sent": "Отправил подарок",
            "question_vip_sent": "Подарил VIP статус",
            "question_premium_sent": "Подарил Telegram Premium",
            "successful_payment": "Совершил покупку",
        }
        last_action = action_map.get(last_log[0], last_log[0].replace("_", " ").capitalize()) if last_log else "нет данных"

        views = await scalar("SELECT COUNT(*) FROM question_link_visits WHERE owner_id=?", (uid,))
        stayed = await scalar("SELECT COUNT(DISTINCT visitor_id) FROM question_link_visits WHERE owner_id=?", (uid,))
        q_received = await scalar("SELECT COUNT(*) FROM anonymous_questions WHERE receiver_id=?", (uid,))
        q_sent = await scalar("SELECT COUNT(*) FROM anonymous_questions WHERE sender_id=?", (uid,))
        revealed_by_user = await scalar("SELECT COUNT(*) FROM anonymous_questions WHERE receiver_id=? AND author_revealed=1", (uid,))
        user_was_revealed = await scalar("SELECT COUNT(*) FROM anonymous_questions WHERE sender_id=? AND author_revealed=1", (uid,))

        gift_received = await scalar("SELECT COUNT(*) FROM purchases WHERE receiver_id=? AND type='question_gift'", (uid,))
        gift_sent = await scalar("SELECT COUNT(*) FROM purchases WHERE buyer_id=? AND type='question_gift'", (uid,))
        stars_received = await scalar("SELECT COALESCE(SUM(price_stars),0) FROM purchases WHERE receiver_id=? AND type='question_stars'", (uid,))
        stars_sent = await scalar("SELECT COALESCE(SUM(price_stars),0) FROM purchases WHERE buyer_id=? AND type='question_stars'", (uid,))
        vip_received = await scalar("SELECT COUNT(*) FROM purchases WHERE receiver_id=? AND type='question_vip'", (uid,))
        vip_sent = await scalar("SELECT COUNT(*) FROM purchases WHERE buyer_id=? AND type='question_vip'", (uid,))
        premium_received = await scalar("SELECT COUNT(*) FROM purchases WHERE receiver_id=? AND type='question_premium'", (uid,))
        premium_sent = await scalar("SELECT COUNT(*) FROM purchases WHERE buyer_id=? AND type='question_premium'", (uid,))

        chat_reveals = await scalar("SELECT COUNT(*) FROM purchases WHERE buyer_id=? AND type='reveal'", (uid,))
        chat_gifts = await scalar("SELECT COUNT(*) FROM purchases WHERE buyer_id=? AND type='gift'", (uid,))
        chat_vip = await scalar("SELECT COUNT(*) FROM purchases WHERE buyer_id=? AND type IN ('vip','vip_subscription')", (uid,))

        total_spent = await scalar("SELECT COALESCE(SUM(price_stars),0) FROM purchases WHERE buyer_id=?", (uid,))
        premium_spent = await scalar("SELECT COALESCE(SUM(price_stars),0) FROM purchases WHERE buyer_id=? AND type='question_premium'", (uid,))
        bot_income = max(0, total_spent - premium_spent)

    text = (
        "👤 <b>Пользователь</b>\n\n"
        f"🆔 ID: <code>{uid}</code>\n"
        f"👤 Имя: <b>{html.escape(full_name)}</b>\n"
        f"📅 Регистрация: <b>{joined}</b>\n"
        f"⭐ VIP: <b>{vip_text}</b>\n\n"
        "🟢 <b>Последняя активность</b>\n"
        f"├ Последний вход: <b>{last_activity}</b>\n"
        f"└ Последнее действие: <b>{html.escape(last_action)}</b>\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "💬 <b>Анонимный чат</b>\n"
        f"├ Диалогов: <b>{completed_dialogs}</b>\n"
        f"├ Раскрытий: <b>{chat_reveals}</b>\n"
        f"├ Подарков: <b>{chat_gifts}</b>\n"
        f"├ VIP: <b>{chat_vip}</b>\n"
        f"└ Жалоб: <b>{complaints}</b>\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "❓ <b>Анонимные вопросы</b>\n\n"
        "🔗 <b>Активность</b>\n"
        f"├ Просмотров: <b>{views}</b>\n"
        f"└ Остались в боте: <b>{stayed}</b>\n\n"
        "❓ <b>Вопросы</b>\n"
        f"├ Получил: <b>{q_received}</b>\n"
        f"├ Отправил: <b>{q_sent}</b>\n"
        f"├ Раскрыл пользователей: <b>{revealed_by_user}</b>\n"
        f"└ Был раскрыт: <b>{user_was_revealed}</b>\n\n"
        "🎁 <b>Подарки</b>\n"
        f"├ Получил: <b>{gift_received}</b>\n"
        f"└ Отправил: <b>{gift_sent}</b>\n\n"
        "⭐ <b>Звёзды</b>\n"
        f"├ Получил: <b>{stars_received} ⭐</b>\n"
        f"└ Отправил: <b>{stars_sent} ⭐</b>\n\n"
        "👑 <b>VIP статус</b>\n"
        f"├ Получил: <b>{vip_received}</b>\n"
        f"└ Подарил: <b>{vip_sent}</b>\n\n"
        "💎 <b>Telegram Premium</b>\n"
        f"├ Получил: <b>{premium_received}</b>\n"
        f"└ Подарил: <b>{premium_sent}</b>\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "💰 <b>Финансы</b>\n"
        f"├ Потратил: <b>{total_spent} ⭐</b>\n"
        f"└ Доход бота: <b>{bot_income} ⭐</b>"
    )

    restriction_kind = "ban" if blocked and not (len(user) > 19 and user[19]) else ("mute" if blocked else "none")
    vip_label = "❌ Снять VIP" if is_vip else "👑 VIP на 30 дней"
    vip_cb = f"admin_cancel_vip_{uid}" if is_vip else f"admin_confirm_vip_{uid}"
    warning_row = [InlineKeyboardButton(text="⚠️ Выдать предупреждение", callback_data=f"warn_{uid}")]
    if warnings > 0:
        warning_row.append(InlineKeyboardButton(text=f"➖ Снять предупреждение ({warnings})", callback_data=f"admin_unwarn_{uid}"))
    rows = [[InlineKeyboardButton(text=vip_label, callback_data=vip_cb)], warning_row]
    if restriction_kind in {"mute", "ban"}:
        rows.append([InlineKeyboardButton(text="✅ Разблокировать", callback_data=f"admin_unblock_{uid}")])
    else:
        rows.append([
            InlineKeyboardButton(text="🔇 Мут 24 часа", callback_data=f"admin_confirm_mute_{uid}"),
            InlineKeyboardButton(text="⛔ Бан", callback_data=f"admin_confirm_ban_{uid}"),
        ])
    rows += [
        [InlineKeyboardButton(text="📜 История", callback_data=f"admin_user_history_{uid}"), InlineKeyboardButton(text="🔄 Обновить", callback_data=f"admin_user_card_{uid}")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="admin_back_to_users")],
    ]
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


async def refresh_admin_user_message(message, user_id: int, prefix: str | None = None):
    user = await db.get_user(user_id)
    if not user:
        await message.edit_text("❌ Пользователь больше не найден.")
        return
    text, kb = await admin_user_card(user)
    if prefix:
        text = f"{prefix}\n\n{text}"
    try:
        await message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await message.answer(text, parse_mode="HTML", reply_markup=kb)

# ---------- ЛОГИКА ТАЙМЕРА НЕАКТИВНОСТИ И НАПОМИНАНИЙ ----------

def reset_inactivity_timer(bot, user_id: int, partner_id: int):
    for uid in (user_id, partner_id):
        if uid in chat_timeout_tasks:
            chat_timeout_tasks[uid].cancel()

    task = asyncio.create_task(inactivity_timer_worker(bot, user_id, partner_id))
    chat_timeout_tasks[user_id] = task
    chat_timeout_tasks[partner_id] = task

async def inactivity_timer_worker(bot, user1_id: int, user2_id: int):
    try:
        await asyncio.sleep(600)  # 10 минут
        
        await db.add_completed_chat_time(user1_id)
        await db.add_completed_chat_time(user2_id)
        await db.end_chat(user1_id)
        chat_timeout_tasks.pop(user1_id, None)
        chat_timeout_tasks.pop(user2_id, None)
        cancel_unread_reminder(user1_id)
        cancel_unread_reminder(user2_id)

        for uid in (user1_id, user2_id):
            try:
                await bot.send_message(
                    uid,
                    "⌛ <b>Диалог завершён из-за неактивности (10 минут).</b>\n\nМожете начать новый поиск!",
                    reply_markup=main_menu(uid in ADMIN_IDS),
                    parse_mode="HTML"
                )
            except Exception:
                pass
        from .advertising import send_ads_to_dialog_users
        await send_ads_to_dialog_users(bot, user1_id, user2_id, f"timeout:{min(user1_id, user2_id)}:{max(user1_id, user2_id)}:{int(datetime.now().timestamp())}")
        for uid in (user1_id, user2_id):
            partner_offer_id = user2_id if uid == user1_id else user1_id
            try:
                await bot.send_message(uid, "Хотите узнать, с кем вы общались?", reply_markup=reveal_offer_kb(partner_offer_id))
            except Exception:
                pass
            await notify_pending_question_activity(bot, uid)
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.exception(
            "Ошибка таймера неактивности: user1=%s, user2=%s",
            user1_id,
            user2_id,
        )



def cancel_inactivity_timer(user_id: int, partner_id: int = None):
    if user_id in chat_timeout_tasks:
        chat_timeout_tasks[user_id].cancel()
        chat_timeout_tasks.pop(user_id, None)
    if partner_id and partner_id in chat_timeout_tasks:
        chat_timeout_tasks[partner_id].cancel()
        chat_timeout_tasks.pop(partner_id, None)

def schedule_unread_reminder(bot, recipient_id: int):
    cancel_unread_reminder(recipient_id)
    task = asyncio.create_task(unread_reminder_worker(bot, recipient_id))
    unread_reminder_tasks[recipient_id] = task

def cancel_unread_reminder(user_id: int):
    if user_id in unread_reminder_tasks:
        unread_reminder_tasks[user_id].cancel()
        unread_reminder_tasks.pop(user_id, None)

async def unread_reminder_worker(bot, recipient_id: int):
    try:
        await asyncio.sleep(180)  # 3 минуты
        if await db.get_partner(recipient_id):
            await bot.send_message(
                recipient_id, 
                "🔔 <b>У вас есть непрочитанное сообщение от собеседника!</b>\n"
                "<i>Ответьте ему, чтобы диалог не прервался.</i>",
                parse_mode="HTML"
            )
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.exception(
            "Ошибка при отправке напоминания: recipient_id=%s",
            recipient_id,
        )
    finally:
        unread_reminder_tasks.pop(recipient_id, None)

def reveal_offer_kb(partner_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Узнать, кто был собеседник", callback_data=f"offer_reveal_{partner_id}")]
    ])

def cancel_search_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👻 Поймать CASPER")],
            [KeyboardButton(text="❌  Отменить поиск")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=True,
    )

BRAND_ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets" / "brand"
BRAND_ASSETS = {
    "main_menu": BRAND_ASSETS_DIR / "main_menu.png",
    "search": BRAND_ASSETS_DIR / "search.png",
    "games": BRAND_ASSETS_DIR / "games.png",
    "profile": BRAND_ASSETS_DIR / "profile.png",
    "invite": BRAND_ASSETS_DIR / "invite.png",
    "admin": BRAND_ASSETS_DIR / "admin.png",
    "advertising": BRAND_ASSETS_DIR / "advertising.png",
    "search_cancelled": BRAND_ASSETS_DIR / "search_cancelled.png",
    "dialog_ended": BRAND_ASSETS_DIR / "dialog_ended.png",
    "questions": BRAND_ASSETS_DIR / "questions.png",
}






def referral_invitation_text(*, compact: bool = False) -> str:
    """Единый текст приглашения для всех реферальных экранов."""
    if compact:
        return (
            "👻 Тебя пригласили в CASPER GO!\n\n"
            "Иногда самые интересные знакомства начинаются совершенно случайно.\n\n"
            "Здесь тебя ждут: анонимное общение, игры, подарки и VIP-возможности.\n\n"
            "Присоединяйся 👇"
        )

    return (
        "👻 Тебя пригласили в CASPER GO!\n\n"
        "Иногда самые интересные знакомства начинаются совершенно случайно.\n\n"
        "Здесь тебя ждут:\n"
        "💬 анонимное общение\n"
        "🎮 игры с собеседниками\n"
        "🎁 подарки и награды\n"
        "💎 VIP-возможности\n\n"
        "Присоединяйся — возможно, твой лучший разговор начнётся именно здесь 👇"
    )

async def build_referral_link(bot, ref_code: str) -> str:
    """Создаёт реферальную ссылку именно на текущего запущенного бота."""
    try:
        bot_info = await bot.get_me()
        username = (bot_info.username or "").strip().lstrip("@")
    except Exception:
        username = BOT_USERNAME.strip().lstrip("@")

    if not username:
        raise RuntimeError("Не удалось определить username текущего Telegram-бота")

    return f"https://t.me/{username}?start=ref_{ref_code}"




async def prepare_referral_data(
    bot,
    user_id: int,
    *,
    compact_invitation: bool = False,
) -> tuple[str, str, dict]:
    """Возвращает реферальную ссылку, ссылку отправки и статистику."""
    ref_code = await db.ensure_ref_code(user_id)
    ref_link = await build_referral_link(bot, ref_code)

    invitation = referral_invitation_text(
        compact=compact_invitation,
    )

    # Ссылка включена в конец текста, чтобы при отправке она не появлялась первой строкой.
    share_text = f"{invitation}\n\n{ref_link}"
    share_url = (
        "https://t.me/share/url?"
        "url="
        f"&text={quote(share_text, safe='')}"
    )

    stats = await db.get_user_referrals_stats(user_id)

    return ref_link, share_url, stats


async def hide_reply_keyboard(message: Message) -> None:
    """Однократно скрывает нижнюю клавиатуру при входе в inline-раздел.

    Служебное сообщение удаляется сразу после применения клавиатуры.
    """
    try:
        service = await message.answer("Открываю раздел…", reply_markup=ReplyKeyboardRemove())
        try:
            await service.delete()
        except Exception:
            pass
    except Exception:
        pass


async def send_brand_card(message: Message, card: str, caption: str, reply_markup=None):
    """Отправляет фирменную карточку CASPER с безопасным текстовым fallback."""
    asset = BRAND_ASSETS.get(card)
    try:
        if asset and asset.exists():
            return await message.answer_photo(
                photo=FSInputFile(asset),
                caption=caption,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
    except Exception as exc:
        await db.log_action(message.from_user.id, "brand_card_error", f"{card}: {exc}")
    return await message.answer(caption, parse_mode="HTML", reply_markup=reply_markup)


async def safe_delete_message(message: Message) -> None:
    """Удаляет именно текущее сообщение, не ломая переход при уже удалённой карточке."""
    try:
        await message.delete()
    except Exception:
        pass


async def notify_pending_question_activity(bot, user_id: int) -> None:
    """Показывает накопленные за активный чат вопросы и ответы, затем сбрасывает флаги."""
    questions_count, answers_count = await db.consume_pending_question_activity(user_id)
    if not questions_count and not answers_count:
        return

    parts = []
    if questions_count:
        word = "вопрос" if questions_count == 1 else ("вопроса" if questions_count in (2, 3, 4) else "вопросов")
        parts.append(
            f"❓ Пока вы общались в анонимном чате, кто-то вне чата задал вам "
            f"<b>{questions_count}</b> новых анонимных {word}."
        )
    if answers_count:
        word = "ответ" if answers_count == 1 else ("ответа" if answers_count in (2, 3, 4) else "ответов")
        parts.append(
            f"💬 Пока вы общались в анонимном чате, вам поступило "
            f"<b>{answers_count}</b> новых {word} на анонимные вопросы."
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📥 Открыть вопросы", callback_data="questions:home")
    ]])
    try:
        await bot.send_message(
            user_id,
            "\n\n".join(parts),
            parse_mode="HTML",
            reply_markup=kb,
        )
    except Exception:
        pass


async def show_main_menu_screen(message: Message, user_id: int) -> Message:
    """Единая точка возврата в главное меню с карточкой и нижней клавиатурой."""
    return await send_brand_card(
        message,
        "main_menu",
        "👻 <b>CASPER</b>\n\nВыберите нужный раздел.",
        main_menu(user_id in ADMIN_IDS),
    )


@router.callback_query(F.data == "nav_main_menu")
async def nav_main_menu_callback(callback: CallbackQuery, state: FSMContext):
    """Возврат из любого inline-раздела в обычное главное меню CASPER."""
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await show_main_menu_screen(callback.message, callback.from_user.id)
    await callback.answer()


async def show_games_screen(message: Message) -> Message:
    """Единый экран выбора одиночных игр."""
    return await send_brand_card(
        message,
        "games",
        "🎮 <b>Мини-игры CASPER</b>\n\nВыберите одиночную игру против CASPER на ⭐ Звёзды:",
        solo_games_menu_kb(),
    )


SEARCH_ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets" / "search"
SEARCH_CARDS = {
    "start": SEARCH_ASSETS_DIR / "search_start.png",
    "waiting": SEARCH_ASSETS_DIR / "search_waiting.png",
    "found": SEARCH_ASSETS_DIR / "search_found.png",
    "timeout": SEARCH_ASSETS_DIR / "search_timeout.png",
}

SEARCH_CAPTIONS = {
    "start": (
        "🔍 <b>CASPER ищет для вас собеседника...</b>\n\n"
        "⌛ Обычно поиск занимает несколько секунд."
    ),
    "waiting": (
        "👻 <b>CASPER активно старается подобрать Вам собеседника...</b>\n\n"
        "Пожалуйста, подождите ещё немного."
    ),
    "found": (
        "👻 <b>CASPER</b>\n\n"
        "🎉 <b>Я нашёл вам собеседника!</b>\n\n"
        "Желаю приятного общения 💜"
    ),
    "timeout": (
        "👻 <b>CASPER пока не смог подобрать вам собеседника.</b>\n\n"
        "Поиск автоматически остановлен.\n"
        "Нажмите «💬 Найти собеседника», чтобы попробовать снова."
    ),
}


async def delete_search_card(bot, user_id: int) -> None:
    message_id = search_card_message_ids.pop(user_id, None)
    if not message_id:
        return
    try:
        await bot.delete_message(user_id, message_id)
    except Exception:
        pass


async def send_search_card(bot, user_id: int, stage: str, reply_markup=None) -> int | None:
    await delete_search_card(bot, user_id)
    try:
        sent = await bot.send_photo(
            chat_id=user_id,
            photo=FSInputFile(SEARCH_CARDS[stage]),
            caption=SEARCH_CAPTIONS[stage],
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
    except Exception as exc:
        await db.log_action(user_id, "search_card_error", f"{stage}: {exc}")
        sent = await bot.send_message(
            user_id,
            SEARCH_CAPTIONS[stage],
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
    search_card_message_ids[user_id] = sent.message_id
    return sent.message_id


def cancel_search_timer(user_id: int):
    task = search_timeout_tasks.pop(user_id, None)
    if task:
        task.cancel()


async def search_timeout_worker(bot, user_id: int):
    try:
        await asyncio.sleep(30)
        if await db.is_in_queue(user_id) and not await db.get_partner(user_id):
            await send_search_card(bot, user_id, "waiting", cancel_search_menu())

        await asyncio.sleep(150)
        if await db.is_in_queue(user_id) and not await db.get_partner(user_id):
            await db.remove_from_queue(user_id)
            await db.log_action(user_id, "queue_timeout", "180_seconds")
            await send_search_card(bot, user_id, "timeout", main_menu(user_id in ADMIN_IDS))
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        await db.log_action(user_id, "search_timeout_error", str(exc))
    finally:
        current = search_timeout_tasks.get(user_id)
        if current is asyncio.current_task():
            search_timeout_tasks.pop(user_id, None)


async def start_searching(message: Message):
    user_id = message.from_user.id
    cancel_search_timer(user_id)
    reset_search_game(user_id)

    if await db.get_partner(user_id):
        await message.answer("❌ Вы уже находитесь в диалоге.")
        return

    partner_id = await db.try_match_user(user_id)

    if partner_id:
        cancel_search_timer(partner_id)
        reset_inactivity_timer(message.bot, user_id, partner_id)
        await db.set_chat_start_time(user_id)
        await db.set_chat_start_time(partner_id)

        failed_users = []
        for uid in (user_id, partner_id):
            try:
                await send_search_card(message.bot, uid, "found", chat_menu())
            except Exception as exc:
                failed_users.append(uid)
                await db.log_action(uid, "match_notification_error", str(exc))
        if failed_users:
            await db.end_chat(user_id)
            if user_id not in failed_users:
                await db.add_to_queue(user_id)
                await send_search_card(message.bot, user_id, "start", cancel_search_menu())
                task = asyncio.create_task(search_timeout_worker(message.bot, user_id))
                task.add_done_callback(_log_background_task_error)
                search_timeout_tasks[user_id] = task
            return
        await db.log_action(user_id, "chat_start_instant", f"with {partner_id}")
    else:
        await db.log_action(user_id, "queue_join")
        await send_search_card(message.bot, user_id, "start", cancel_search_menu())
        task = asyncio.create_task(search_timeout_worker(message.bot, user_id))
        task.add_done_callback(_log_background_task_error)
        search_timeout_tasks[user_id] = task


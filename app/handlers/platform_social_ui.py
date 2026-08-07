from __future__ import annotations

import html

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app import database as db
from .shared import router


def _community_keyboard(unread: int) -> InlineKeyboardMarkup:
    badge = f" ({unread})" if unread else ""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Репутация", callback_data="platform_reputation")],
        [InlineKeyboardButton(text=f"🔔 Уведомления{badge}", callback_data="platform_notifications")],
        [InlineKeyboardButton(text="🤝 Контакты", callback_data="platform_community_contacts")],
        [InlineKeyboardButton(text="⬅️ Ещё", callback_data="commercial_more_back")],
    ])


def _back_keyboard(callback_data: str = "platform_community") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Сообщество", callback_data=callback_data)],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="nav_main_menu")],
    ])


async def _render_community(target: Message, user_id: int, *, edit: bool = False) -> None:
    unread = await db.unread_notification_count(user_id)
    reputation = await db.get_reputation_summary(user_id)
    text = (
        "<b>🌐 Сообщество</b>\n\n"
        f"⭐ Положительных оценок: <b>{reputation.positive_percent}%</b>\n"
        f"💬 Всего оценок: <b>{reputation.total}</b>\n"
        f"🔔 Новых уведомлений: <b>{unread}</b>\n\n"
        "Здесь собраны социальная активность, доверие и важные события аккаунта."
    )
    if edit:
        await target.edit_text(text, parse_mode="HTML", reply_markup=_community_keyboard(unread))
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=_community_keyboard(unread))


@router.message(F.text == "🌐 Сообщество")
async def community_message(message: Message) -> None:
    await _render_community(message, message.from_user.id)


@router.callback_query(F.data == "platform_community")
async def community_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    await _render_community(callback.message, callback.from_user.id, edit=True)


@router.callback_query(F.data == "platform_reputation")
async def reputation_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    summary = await db.get_reputation_summary(callback.from_user.id)
    if summary.total >= 20 and summary.positive_percent >= 90:
        badge = "🏅 Надёжный собеседник"
    elif summary.total >= 5 and summary.positive_percent >= 75:
        badge = "✨ Хорошая репутация"
    else:
        badge = "🌱 Репутация формируется"
    await callback.message.edit_text(
        "<b>⭐ Репутация</b>\n\n"
        f"{badge}\n\n"
        f"👍 Отлично: <b>{summary.positive}</b>\n"
        f"🙂 Нормально: <b>{summary.neutral}</b>\n"
        f"👎 Не понравилось: <b>{summary.negative}</b>\n"
        f"📊 Положительных: <b>{summary.positive_percent}%</b>\n\n"
        "Оценки принимаются только после завершённых диалогов и не раскрывают личность автора.",
        parse_mode="HTML",
        reply_markup=_back_keyboard(),
    )


@router.callback_query(F.data == "platform_notifications")
async def notifications_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    items = await db.get_notifications(callback.from_user.id, 10)
    if not items:
        body = "Пока нет уведомлений. Здесь появятся награды, достижения и системные события."
    else:
        lines = []
        for _id, kind, title, notification_body, is_read, created_at in items:
            marker = "▫️" if is_read else "🔹"
            lines.append(
                f"{marker} <b>{html.escape(str(title))}</b>\n"
                f"{html.escape(str(notification_body))}"
            )
        body = "\n\n".join(lines)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Прочитать всё", callback_data="platform_notifications_read")],
        [InlineKeyboardButton(text="⬅️ Сообщество", callback_data="platform_community")],
    ])
    await callback.message.edit_text(
        f"<b>🔔 Уведомления</b>\n\n{body}",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "platform_notifications_read")
async def notifications_read_callback(callback: CallbackQuery) -> None:
    changed = await db.mark_notifications_read(callback.from_user.id)
    await callback.answer(f"Прочитано: {changed}")
    await notifications_callback(callback)

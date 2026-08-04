from __future__ import annotations

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery

from app.core.ui_copy import metric, screen, section
from app.core.ui_labels import ButtonText

from .shared import ADMIN_IDS, admin_panel, db, router, send_brand_card, safe_delete_message


def admin_users_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📡 Центр управления", callback_data="admin_ops_dashboard")],
        [InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="admin_user_search")],
        [
            InlineKeyboardButton(text="⚠️ С предупреждениями", callback_data="admin_warned_list"),
            InlineKeyboardButton(text="🔒 С ограничениями", callback_data="admin_restricted_list"),
        ],
        [InlineKeyboardButton(text="📥 Скачать базу пользователей", callback_data="admin_download_users")],
        [InlineKeyboardButton(text=ButtonText.BACK, callback_data="admin_back_to_panel")],
    ])


def admin_home_text() -> str:
    return screen(
        "⚙️ Панель управления",
        intro=(
            "Быстрый доступ к пользователям, рассылкам, подаркам, "
            "платежам, модерации и живому состоянию бота."
        ),
        sections=(
            section("Основное", (
                "📡 Центр управления и оперативные показатели",
                "👥 Пользователи и статистика",
                "📨 Рассылки и рекламные кампании",
                "🎁 Подарки и заявки на вывод",
                "🛡 Модерация и системные настройки",
            )),
        ),
        footer="Выберите раздел на клавиатуре ниже.",
    )


def admin_statistics_text(stats: dict) -> str:
    return screen(
        "📊 Состояние CASPER",
        intro=(
            f"Сейчас в очереди {stats['queue_count']}, "
            f"активных диалогов — {stats['active_chats']}."
        ),
        sections=(
            section("Сегодня", (
                metric("🆕", "Новых пользователей", stats["new_today"]),
                metric("🎁", "Подарков отправлено", stats["gifts_today"]),
            )),
            section("Пользователи", (
                metric("👥", "Всего", stats["total_users"]),
                metric("👑", "Активных VIP", stats["active_vip_users"]),
                metric("🛍", "VIP-покупок", stats["vip_purchases"]),
            )),
            section("Монетизация и безопасность", (
                metric("⭐", "Получено звёзд", stats["total_stars"]),
                metric("🔍", "Раскрытий", stats["reveal_count"]),
                metric("🚨", "Жалоб", stats["total_complaints"]),
                metric("🎁", "Подарков всего", stats["total_gifts_sent"]),
            )),
        ),
        footer="Ниже доступны центр управления, поиск, ограничения и выгрузка базы.",
    )


@router.message(F.text.in_({"🔧 Админ-панель", "⚙️ Админ-панель CASPER", "⚙️ Панель управления"}))
async def admin_panel_entry(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    await send_brand_card(message, "admin", admin_home_text(), admin_panel())


@router.message(F.text.in_({"📊 Статистика", "📊 Статистика и пользователи", "👥 Пользователи"}))
async def admin_statistics_entry(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    stats = await db.get_statistics()
    await message.answer(
        admin_statistics_text(stats),
        parse_mode="HTML",
        reply_markup=admin_users_keyboard(),
    )


@router.callback_query(F.data == "admin_back_to_panel")
async def admin_back_to_panel(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    await callback.answer()
    await safe_delete_message(callback.message)
    await send_brand_card(callback.message, "admin", admin_home_text(), admin_panel())

from __future__ import annotations

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery

from app.core.ui_copy import metric, screen, section
from app.core.ui_labels import ButtonText, ScreenTitle

from .shared import ADMIN_IDS, admin_panel, db, router, send_brand_card, safe_delete_message


def admin_users_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="admin_user_search"),
            InlineKeyboardButton(text="📥 Скачать базу", callback_data="admin_download_users"),
        ],
        [
            InlineKeyboardButton(text="⚠️ Предупреждения", callback_data="admin_warned_list"),
            InlineKeyboardButton(text="🔒 Ограничения", callback_data="admin_restricted_list"),
        ],
        [InlineKeyboardButton(text=ButtonText.BACK, callback_data="admin_back_to_panel")],
    ])


def admin_home_text() -> str:
    return screen(
        ScreenTitle.ADMIN,
        intro="Управление пользователями, рассылками, платежами и настройками.",
        footer="Выберите раздел.",
    )


def admin_statistics_text(stats: dict) -> str:
    return screen(
        "📊 Статистика",
        sections=(
            section("Пользователи", (
                metric("👥", "Всего", stats["total_users"]),
                metric("🆕", "Новых сегодня", stats["new_today"]),
                metric("👑", "Активных VIP", stats["active_vip_users"]),
                metric("🛍", "VIP-покупок", stats["vip_purchases"]),
            )),
            section("Общение", (
                metric("🔎", "В очереди", stats["queue_count"]),
                metric("💬", "Активных диалогов", stats["active_chats"]),
            )),
            section("Активность", (
                metric("🎁", "Подарков отправлено", stats["total_gifts_sent"]),
                metric("📅", "Подарков за сутки", stats["gifts_today"]),
                metric("⭐", "Получено звёзд", stats["total_stars"]),
                metric("🔍", "Раскрытий", stats["reveal_count"]),
                metric("🚨", "Жалоб", stats["total_complaints"]),
            )),
        ),
        footer="Действия с пользователями доступны ниже.",
    )


@router.message(F.text.in_({"🔧 Админ-панель", "⚙️ Админ-панель CASPER"}))
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

from __future__ import annotations

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from .service_menu import NEWS_CHANNEL_USERNAME, SUPPORT_USERNAME
from .shared import ADMIN_IDS, router


def _more_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="☀️ Мой день", callback_data="commercial_daily_hub"),
            InlineKeyboardButton(text="🌐 Сообщество", callback_data="platform_community"),
        ],
        [
            InlineKeyboardButton(text="📢 Новости", url=f"https://t.me/{NEWS_CHANNEL_USERNAME}"),
            InlineKeyboardButton(text="🛟 Поддержка", url=f"https://t.me/{SUPPORT_USERNAME}"),
        ],
        [
            InlineKeyboardButton(text="📣 Реклама", callback_data="commercial_ads_info"),
            InlineKeyboardButton(text="🔐 Приватность", callback_data="service_privacy"),
        ],
        [InlineKeyboardButton(text="ℹ️ О проекте", callback_data="service_about")],
        [InlineKeyboardButton(text="✖️ Закрыть", callback_data="service_message_delete")],
    ])


def _admin_sections_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ Пульс", callback_data="admin_platform_pulse")],
        [InlineKeyboardButton(text="📡 Операции", callback_data="admin_ops_dashboard")],
        [
            InlineKeyboardButton(text="📈 Аналитика", callback_data="admin_retention_dashboard"),
            InlineKeyboardButton(text="🩺 Система", callback_data="admin_platform_health"),
        ],
        [
            InlineKeyboardButton(text="🚨 Модерация", callback_data="admin_complaints_dashboard"),
            InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_user_search"),
        ],
        [
            InlineKeyboardButton(text="📨 Коммуникации", callback_data="admin_broadcast"),
            InlineKeyboardButton(text="🧾 Журнал", callback_data="admin_audit_journal"),
        ],
        [InlineKeyboardButton(text="⬅️ Полная админка", callback_data="admin_back_to_panel")],
    ])


@router.message(F.text == "✨ Ещё")
async def commercial_more(message: Message) -> None:
    await message.answer(
        "<b>✨ Ещё</b>\n\nСообщество, новости, поддержка и информация о сервисе — в одном месте.",
        parse_mode="HTML",
        reply_markup=_more_keyboard(),
    )


@router.callback_query(F.data == "commercial_ads_info")
async def commercial_ads_info(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "<b>📣 Реклама в CASPER GO</b>\n\n"
        "Размещение обсуждается индивидуально. Укажите формат, срок и желаемый охват.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛟 Обсудить размещение", url=f"https://t.me/{SUPPORT_USERNAME}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="commercial_more_back")],
        ]),
    )


@router.callback_query(F.data == "commercial_more_back")
async def commercial_more_back(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "<b>✨ Ещё</b>\n\nСообщество, новости, поддержка и информация о сервисе — в одном месте.",
        parse_mode="HTML",
        reply_markup=_more_keyboard(),
    )


@router.message(F.text.in_({"⚙️ Админка", "⚙️ Управление"}))
async def commercial_admin_hub(message: Message) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer(
        "<b>⚙️ Управление CASPER</b>\n\n"
        "Операции, аналитика, модерация и коммуникации разделены по задачам.",
        parse_mode="HTML",
        reply_markup=_admin_sections_keyboard(),
    )


@router.callback_query(F.data == "admin_commercial_hub")
async def admin_commercial_hub(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer()
    await callback.message.edit_text(
        "<b>⚙️ Управление CASPER</b>\n\n"
        "Операции, аналитика, модерация и коммуникации разделены по задачам.",
        parse_mode="HTML",
        reply_markup=_admin_sections_keyboard(),
    )

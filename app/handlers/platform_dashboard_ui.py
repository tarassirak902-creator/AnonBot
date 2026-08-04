from __future__ import annotations

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.core.ui_copy import metric, screen, section
from app.services.platform_insights import (
    load_admin_operational_snapshot,
    load_recent_anonymous_contacts,
    remove_anonymous_contact,
)

from .shared import ADMIN_IDS, router


def _admin_ops_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_ops_refresh"),
            InlineKeyboardButton(text="🩺 Здоровье", callback_data="admin_platform_health"),
        ],
        [
            InlineKeyboardButton(text="📈 Удержание", callback_data="admin_retention_dashboard"),
            InlineKeyboardButton(text="🧾 Журнал", callback_data="admin_audit_journal"),
        ],
        [
            InlineKeyboardButton(text="🚨 Жалобы", callback_data="admin_complaints_dashboard"),
            InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_user_search"),
        ],
        [InlineKeyboardButton(text="📨 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="⬅️ Админка", callback_data="admin_back_to_panel")],
    ])


async def _admin_ops_text() -> str:
    stats = await load_admin_operational_snapshot()
    negative_share = 0
    if stats["ratings_24h"]:
        negative_share = round(stats["negative_ratings_24h"] * 100 / stats["ratings_24h"])
    return screen(
        "📡 Центр управления",
        intro="Живое состояние пользователей, диалогов и модерации.",
        sections=(
            section("Сейчас", (
                metric("🔎", "В очереди", stats["queue"]),
                metric("💬", "Активных связей", stats["active_chats"]),
                metric("🤝", "Взаимных контактов", stats["mutual_contacts"]),
                metric("⏳", "Ожидают взаимности", stats["pending_reconnects"]),
            )),
            section("Активность", (
                metric("🆕", "Новых за 24 часа", stats["users_24h"]),
                metric("📅", "Новых за 7 дней", stats["users_7d"]),
                metric("⭐", "Оценок за 24 часа", stats["ratings_24h"]),
                metric("👎", "Негативных оценок", f"{negative_share}%"),
            )),
            section("Безопасность", (
                metric("🚨", "Жалоб всего", stats["complaints"]),
                "При росте негативных оценок проверьте жалобы и здоровье платформы.",
            )),
        ),
        footer="Журнал показывает агрегаты действий без содержимого переписки.",
    )


@router.message(F.text.in_({"📡 Центр", "📡 Управление", "📊 Мониторинг"}))
async def admin_operations_message(message: Message) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer(await _admin_ops_text(), parse_mode="HTML", reply_markup=_admin_ops_keyboard())


@router.callback_query(F.data.in_({"admin_ops_dashboard", "admin_ops_refresh"}))
async def admin_operations_callback(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer("Обновлено" if callback.data == "admin_ops_refresh" else None)
    await callback.message.edit_text(
        await _admin_ops_text(), parse_mode="HTML", reply_markup=_admin_ops_keyboard()
    )


def _contacts_keyboard(items: list[dict[str, object]]) -> InlineKeyboardMarkup:
    rows = []
    for item in items:
        rows.append([
            InlineKeyboardButton(
                text=f"🗑 Удалить {item['label']}",
                callback_data=f"community_contact_remove:{item['contact_id']}",
            )
        ])
    rows.append([InlineKeyboardButton(text="⬅️ Профиль", callback_data="profile_refresh")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _render_contacts(callback: CallbackQuery) -> None:
    items = await load_recent_anonymous_contacts(callback.from_user.id)
    if items:
        lines = [f"• <b>{item['label']}</b>" for item in items]
        body = "\n".join(lines)
    else:
        body = "Пока нет взаимно сохранённых собеседников."
    await callback.message.edit_text(
        "<b>🤝 Мои контакты</b>\n\n"
        f"{body}\n\n"
        "Имена и Telegram-профили не раскрываются.",
        parse_mode="HTML",
        reply_markup=_contacts_keyboard(items),
    )


@router.callback_query(F.data == "community_contacts_list")
async def community_contacts_list(callback: CallbackQuery) -> None:
    await callback.answer()
    await _render_contacts(callback)


@router.callback_query(F.data.startswith("community_contact_remove:"))
async def community_contact_remove(callback: CallbackQuery) -> None:
    try:
        contact_id = int(callback.data.split(":", 1)[1])
    except (TypeError, ValueError):
        await callback.answer("Некорректный контакт", show_alert=True)
        return
    removed = await remove_anonymous_contact(callback.from_user.id, contact_id)
    await callback.answer("Контакт удалён" if removed else "Контакт уже удалён")
    await _render_contacts(callback)

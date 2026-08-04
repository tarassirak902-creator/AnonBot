from __future__ import annotations

import aiosqlite
from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.database.repository import DB_PATH
from .shared import db, router


def _connections_keyboard(enabled: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=("🤝 Сохранение: вкл" if enabled else "🚫 Сохранение: выкл"),
            callback_data="community_reconnect_toggle",
        )],
        [InlineKeyboardButton(text="⬅️ Профиль", callback_data="profile_refresh")],
    ])


async def _connections_total(user_id: int) -> int:
    await db.ensure_community_schema()
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        row = await (
            await conn.execute(
                """SELECT COUNT(DISTINCT CASE
                       WHEN requester_id=? THEN target_id ELSE requester_id END)
                   FROM reconnect_requests
                  WHERE status='accepted' AND (requester_id=? OR target_id=?)""",
                (user_id, user_id, user_id),
            )
        ).fetchone()
    return int(row[0] or 0) if row else 0


async def _edit_connections(callback: CallbackQuery) -> None:
    enabled = await db.is_reconnect_allowed(callback.from_user.id)
    total = await _connections_total(callback.from_user.id)
    status = "разрешено" if enabled else "запрещено"
    await callback.message.edit_text(
        "<b>🤝 Сохранённые контакты</b>\n\n"
        f"Взаимных сохранений: <b>{total}</b>\n"
        f"Новые сохранения: <b>{status}</b>\n\n"
        "Контакт появляется только после взаимного согласия. Личность остаётся скрытой.",
        parse_mode="HTML",
        reply_markup=_connections_keyboard(enabled),
    )


@router.callback_query(F.data == "community_connections")
async def community_connections(callback: CallbackQuery):
    await callback.answer()
    await _edit_connections(callback)


@router.callback_query(F.data == "community_reconnect_toggle")
async def community_reconnect_toggle(callback: CallbackQuery):
    enabled = not await db.is_reconnect_allowed(callback.from_user.id)
    await db.set_reconnect_allowed(callback.from_user.id, enabled)
    await callback.answer("Настройка сохранена")
    await _edit_connections(callback)

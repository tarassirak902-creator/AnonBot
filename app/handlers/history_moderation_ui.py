from __future__ import annotations

import html
from datetime import datetime

import aiosqlite
from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.database.repository import DB_PATH
from .shared import ADMIN_IDS, router


async def _table_exists(conn: aiosqlite.Connection, table: str) -> bool:
    row = await (
        await conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
    ).fetchone()
    return row is not None


def _anonymous_label(user_id: int) -> str:
    return f"Собеседник #{abs(int(user_id)) % 10000:04d}"


def _format_time(value: object) -> str:
    if not value:
        return "дата неизвестна"
    text = str(value)
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y · %H:%M")
    except (TypeError, ValueError):
        return text[:16]


async def _load_dialog_history(user_id: int, limit: int = 10) -> list[tuple[int, str]]:
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        if not await _table_exists(conn, "recent_partners"):
            return []
        rows = await (
            await conn.execute(
                "SELECT partner_id,last_chat_at FROM recent_partners "
                "WHERE user_id=? ORDER BY last_chat_at DESC LIMIT ?",
                (user_id, limit),
            )
        ).fetchall()
    return [(int(row[0]), str(row[1] or "")) for row in rows]


@router.callback_query(F.data == "community_dialog_history")
async def community_dialog_history(callback: CallbackQuery) -> None:
    await callback.answer()
    items = await _load_dialog_history(callback.from_user.id)
    if items:
        lines = [
            f"• <b>{_anonymous_label(partner_id)}</b>\n  {_format_time(last_chat_at)}"
            for partner_id, last_chat_at in items
        ]
        body = "\n\n".join(lines)
    else:
        body = "История пока пуста. Она появится после завершённых диалогов."
    await callback.message.edit_text(
        "<b>🕘 История знакомств</b>\n\n"
        f"{body}\n\n"
        "Содержимое переписки и Telegram-профили не сохраняются.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🤝 Контакты", callback_data="community_connections")],
            [InlineKeyboardButton(text="⬅️ Профиль", callback_data="profile_refresh")],
        ]),
    )


async def _ensure_complaint_reviews(conn: aiosqlite.Connection) -> None:
    await conn.execute(
        "CREATE TABLE IF NOT EXISTS complaint_reviews ("
        "complaint_id INTEGER PRIMARY KEY, admin_id INTEGER NOT NULL, "
        "reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )


async def _load_complaints(limit: int = 10) -> list[dict[str, object]]:
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        if not await _table_exists(conn, "complaints"):
            return []
        await _ensure_complaint_reviews(conn)
        rows = await (
            await conn.execute(
                "SELECT c.id,c.reporter_id,c.reported_id,c.reason,c.timestamp,"
                "CASE WHEN r.complaint_id IS NULL THEN 0 ELSE 1 END "
                "FROM complaints c LEFT JOIN complaint_reviews r ON r.complaint_id=c.id "
                "ORDER BY c.id DESC LIMIT ?",
                (limit,),
            )
        ).fetchall()
        await conn.commit()
    return [
        {
            "id": int(row[0]),
            "reporter_id": int(row[1] or 0),
            "reported_id": int(row[2] or 0),
            "reason": str(row[3] or "Без причины"),
            "timestamp": str(row[4] or ""),
            "reviewed": bool(row[5]),
        }
        for row in rows
    ]


def _complaints_keyboard(items: list[dict[str, object]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for item in items[:8]:
        marker = "✅" if item["reviewed"] else "🚨"
        rows.append([
            InlineKeyboardButton(
                text=f"{marker} Жалоба #{item['id']}",
                callback_data=f"admin_complaint_view:{item['id']}",
            )
        ])
    rows.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_complaints_dashboard")])
    rows.append([InlineKeyboardButton(text="⬅️ Центр", callback_data="admin_ops_dashboard")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _render_complaints(callback: CallbackQuery) -> None:
    items = await _load_complaints()
    pending = sum(not bool(item["reviewed"]) for item in items)
    text = (
        "<b>🚨 Очередь жалоб</b>\n\n"
        f"Непроверенных среди последних: <b>{pending}</b>\n"
        f"Показано записей: <b>{len(items)}</b>\n\n"
        "Открой жалобу, проверь данные и затем отметь её просмотренной."
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=_complaints_keyboard(items))


@router.callback_query(F.data.in_({"admin_complaints", "admin_complaints_dashboard"}))
async def admin_complaints_dashboard(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer()
    await _render_complaints(callback)


@router.callback_query(F.data.startswith("admin_complaint_view:"))
async def admin_complaint_view(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        return
    try:
        complaint_id = int(callback.data.split(":", 1)[1])
    except (TypeError, ValueError):
        await callback.answer("Некорректная жалоба", show_alert=True)
        return
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await _ensure_complaint_reviews(conn)
        row = await (
            await conn.execute(
                "SELECT c.reporter_id,c.reported_id,c.reason,c.timestamp,"
                "CASE WHEN r.complaint_id IS NULL THEN 0 ELSE 1 END "
                "FROM complaints c LEFT JOIN complaint_reviews r ON r.complaint_id=c.id "
                "WHERE c.id=?",
                (complaint_id,),
            )
        ).fetchone()
        await conn.commit()
    if not row:
        await callback.answer("Жалоба не найдена", show_alert=True)
        return
    reviewed = bool(row[4])
    reason = html.escape(str(row[2] or "Без причины"))
    await callback.answer()
    await callback.message.edit_text(
        f"<b>🚨 Жалоба #{complaint_id}</b>\n\n"
        f"Отправитель: <code>{int(row[0] or 0)}</code>\n"
        f"На пользователя: <code>{int(row[1] or 0)}</code>\n"
        f"Причина: <b>{reason}</b>\n"
        f"Время: {_format_time(row[3])}\n"
        f"Статус: {'✅ проверено' if reviewed else '⏳ ожидает проверки'}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Отметить проверенной",
                callback_data=f"admin_complaint_review:{complaint_id}",
            )] if not reviewed else [],
            [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_user_search")],
            [InlineKeyboardButton(text="⬅️ Жалобы", callback_data="admin_complaints_dashboard")],
        ]),
    )


@router.callback_query(F.data.startswith("admin_complaint_review:"))
async def admin_complaint_review(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        return
    try:
        complaint_id = int(callback.data.split(":", 1)[1])
    except (TypeError, ValueError):
        await callback.answer("Некорректная жалоба", show_alert=True)
        return
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await _ensure_complaint_reviews(conn)
        await conn.execute(
            "INSERT OR REPLACE INTO complaint_reviews(complaint_id,admin_id,reviewed_at) "
            "VALUES (?,?,CURRENT_TIMESTAMP)",
            (complaint_id, callback.from_user.id),
        )
        await conn.commit()
    await callback.answer("Жалоба отмечена проверенной")
    callback.data = f"admin_complaint_view:{complaint_id}"
    await admin_complaint_view(callback)

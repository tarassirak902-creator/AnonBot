from __future__ import annotations

from datetime import datetime, timedelta, timezone

import aiosqlite
from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.database.repository import DB_PATH
from .shared import ADMIN_IDS, router


WEEKLY_TARGET = 5
WEEKLY_REWARD = 15


async def _table_exists(conn: aiosqlite.Connection, table: str) -> bool:
    row = await (
        await conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
    ).fetchone()
    return row is not None


async def _column_exists(conn: aiosqlite.Connection, table: str, column: str) -> bool:
    if not await _table_exists(conn, table):
        return False
    rows = await (await conn.execute(f"PRAGMA table_info({table})")).fetchall()
    return column in {str(row[1]) for row in rows}


def _week_key(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    year, week, _ = current.isocalendar()
    return f"{year}-W{week:02d}"


async def _weekly_progress(user_id: int) -> tuple[int, bool]:
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    progress = 0
    claimed = False
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        if await _table_exists(conn, "recent_partners"):
            timestamp_column = "last_chat_at" if await _column_exists(conn, "recent_partners", "last_chat_at") else None
            if timestamp_column:
                row = await (
                    await conn.execute(
                        f"SELECT COUNT(*) FROM recent_partners WHERE user_id=? AND {timestamp_column}>=?",
                        (user_id, since),
                    )
                ).fetchone()
                progress = int(row[0] or 0) if row else 0
        if await _table_exists(conn, "weekly_event_claims"):
            row = await (
                await conn.execute(
                    "SELECT 1 FROM weekly_event_claims WHERE user_id=? AND week_key=?",
                    (user_id, _week_key()),
                )
            ).fetchone()
            claimed = row is not None
    return min(progress, WEEKLY_TARGET), claimed


async def _render_event(callback: CallbackQuery) -> None:
    progress, claimed = await _weekly_progress(callback.from_user.id)
    completed = progress >= WEEKLY_TARGET
    if claimed:
        status = "✅ Награда уже получена"
    elif completed:
        status = "🎁 Цель выполнена — забери награду"
    else:
        status = f"⏳ Прогресс: {progress}/{WEEKLY_TARGET}"
    rows: list[list[InlineKeyboardButton]] = []
    if completed and not claimed:
        rows.append([
            InlineKeyboardButton(
                text=f"🎁 Забрать {WEEKLY_REWARD} ⭐",
                callback_data="weekly_event_claim",
            )
        ])
    rows.extend([
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="weekly_event_hub")],
        [InlineKeyboardButton(text="⬅️ Профиль", callback_data="profile_refresh")],
    ])
    text = (
        "<b>🎪 Событие недели</b>\n\n"
        f"Познакомься с <b>{WEEKLY_TARGET}</b> новыми собеседниками за 7 дней.\n"
        f"Награда: <b>{WEEKLY_REWARD} ⭐</b>\n\n"
        f"{status}\n\n"
        "Учитывается только факт завершённого знакомства. Содержимое переписки не анализируется."
    )
    await callback.answer()
    try:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        )
    except Exception:
        await callback.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        )


@router.callback_query(F.data == "weekly_event_hub")
async def weekly_event_hub(callback: CallbackQuery) -> None:
    await _render_event(callback)


@router.callback_query(F.data == "weekly_event_claim")
async def weekly_event_claim(callback: CallbackQuery) -> None:
    progress, _ = await _weekly_progress(callback.from_user.id)
    if progress < WEEKLY_TARGET:
        await callback.answer("Сначала выполни цель", show_alert=True)
        return
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("BEGIN IMMEDIATE")
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS weekly_event_claims ("
            "user_id INTEGER NOT NULL, week_key TEXT NOT NULL, reward INTEGER NOT NULL, "
            "claimed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, "
            "PRIMARY KEY(user_id, week_key))"
        )
        cursor = await conn.execute(
            "INSERT OR IGNORE INTO weekly_event_claims(user_id,week_key,reward) VALUES (?,?,?)",
            (callback.from_user.id, _week_key(), WEEKLY_REWARD),
        )
        if cursor.rowcount:
            if await _table_exists(conn, "users") and await _column_exists(conn, "users", "stars_balance"):
                await conn.execute(
                    "UPDATE users SET stars_balance=COALESCE(stars_balance,0)+? WHERE user_id=?",
                    (WEEKLY_REWARD, callback.from_user.id),
                )
            await conn.commit()
            await callback.answer(f"Начислено {WEEKLY_REWARD} ⭐", show_alert=True)
        else:
            await conn.rollback()
            await callback.answer("Награда уже получена")
    await _render_event(callback)


async def _audit_text() -> str:
    counts: list[tuple[str, int]] = []
    total_24h = 0
    unique_users = 0
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        if await _table_exists(conn, "logs"):
            has_action = await _column_exists(conn, "logs", "action")
            has_timestamp = await _column_exists(conn, "logs", "timestamp")
            has_user = await _column_exists(conn, "logs", "user_id")
            if has_action and has_timestamp:
                rows = await (
                    await conn.execute(
                        "SELECT COALESCE(action,'unknown'),COUNT(*) FROM logs "
                        "WHERE timestamp>=? GROUP BY action ORDER BY COUNT(*) DESC LIMIT 10",
                        (since,),
                    )
                ).fetchall()
                counts = [(str(row[0]), int(row[1] or 0)) for row in rows]
                total_24h = sum(value for _, value in counts)
            if has_user and has_timestamp:
                row = await (
                    await conn.execute(
                        "SELECT COUNT(DISTINCT user_id) FROM logs WHERE timestamp>=?",
                        (since,),
                    )
                ).fetchone()
                unique_users = int(row[0] or 0) if row else 0
    lines = "\n".join(f"• <code>{action}</code> — <b>{count}</b>" for action, count in counts)
    if not lines:
        lines = "Событий за последние 24 часа пока нет."
    return (
        "<b>🧾 Журнал платформы</b>\n\n"
        f"Событий за 24 часа: <b>{total_24h}</b>\n"
        f"Затронуто пользователей: <b>{unique_users}</b>\n\n"
        f"<b>Основные действия</b>\n{lines}\n\n"
        "Показываются только агрегаты действий. Тексты сообщений и переписка не выводятся."
    )


def _audit_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_audit_journal")],
        [InlineKeyboardButton(text="📡 Центр", callback_data="admin_ops_dashboard")],
        [InlineKeyboardButton(text="⬅️ Админка", callback_data="admin_back_to_panel")],
    ])


@router.message(F.text.in_({"🧾 Журнал", "🧾 Аудит"}))
async def admin_audit_message(message: Message) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer(await _audit_text(), parse_mode="HTML", reply_markup=_audit_keyboard())


@router.callback_query(F.data == "admin_audit_journal")
async def admin_audit_journal(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer("Обновлено")
    text = await _audit_text()
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=_audit_keyboard())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=_audit_keyboard())

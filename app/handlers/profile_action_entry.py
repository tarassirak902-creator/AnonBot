from __future__ import annotations

from datetime import datetime, timedelta

import aiosqlite
from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.database.repository import DB_PATH
from .shared import router


async def _table_exists(conn: aiosqlite.Connection, name: str) -> bool:
    row = await (await conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    )).fetchone()
    return row is not None


async def _column_exists(conn: aiosqlite.Connection, table: str, column: str) -> bool:
    if not await _table_exists(conn, table):
        return False
    rows = await (await conn.execute(f"PRAGMA table_info({table})")).fetchall()
    return column in {str(row[1]) for row in rows}


def _profile_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Профиль", callback_data="profile_refresh")],
    ])


async def _safe_edit(callback: CallbackQuery, text: str, keyboard: InlineKeyboardMarkup) -> None:
    await callback.answer()
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data == "engagement_missions")
async def profile_missions_entry(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    today = datetime.utcnow().date().isoformat()
    completed_dialogs = 0
    messages_count = 0
    claimed: set[str] = set()

    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        if await _table_exists(conn, "users"):
            has_dialogs = await _column_exists(conn, "users", "completed_dialogs")
            has_messages = await _column_exists(conn, "users", "messages_count")
            fields = []
            if has_dialogs:
                fields.append("completed_dialogs")
            if has_messages:
                fields.append("messages_count")
            if fields:
                row = await (await conn.execute(
                    f"SELECT {','.join(fields)} FROM users WHERE user_id=?",
                    (user_id,),
                )).fetchone()
                if row:
                    pos = 0
                    if has_dialogs:
                        completed_dialogs = int(row[pos] or 0)
                        pos += 1
                    if has_messages:
                        messages_count = int(row[pos] or 0)
        if await _table_exists(conn, "mission_claims"):
            rows = await (await conn.execute(
                "SELECT mission_code FROM mission_claims WHERE user_id=? AND claim_date=?",
                (user_id, today),
            )).fetchall()
            claimed = {str(row[0]) for row in rows}

    missions = [
        ("dialog", "Завершить диалог", min(completed_dialogs, 1), 1, 3),
        ("messages", "Отправить 10 сообщений", min(messages_count, 10), 10, 2),
        ("visit", "Открыть профиль", 1, 1, 1),
    ]
    lines = []
    rows = []
    for code, title, progress, target, reward in missions:
        done = progress >= target
        is_claimed = code in claimed
        status = "✅ получено" if is_claimed else ("🎁 готово" if done else f"⏳ {progress}/{target}")
        lines.append(f"• <b>{title}</b> — {status} · {reward} ⭐")
        if done and not is_claimed:
            rows.append([InlineKeyboardButton(
                text=f"🎁 Забрать {reward} ⭐",
                callback_data=f"engagement_mission_claim:{code}",
            )])
    rows.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="engagement_missions")])
    rows.append([InlineKeyboardButton(text="⬅️ Профиль", callback_data="profile_refresh")])
    await _safe_edit(
        callback,
        "<b>🎯 Задания на сегодня</b>\n\n" + "\n".join(lines)
        + "\n\nПрогресс отображается безопасно даже после обновления старой базы.",
        InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data == "user_activity_center")
async def profile_activity_entry(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    stats = {"dialogs": 0, "messages": 0, "seconds": 0, "contacts": 0}
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        if await _table_exists(conn, "users"):
            columns = {
                row[1] for row in await (await conn.execute("PRAGMA table_info(users)")).fetchall()
            }
            selected = [c for c in ("completed_dialogs", "messages_count", "chat_time_seconds") if c in columns]
            if selected:
                row = await (await conn.execute(
                    f"SELECT {','.join(selected)} FROM users WHERE user_id=?",
                    (user_id,),
                )).fetchone()
                if row:
                    mapping = dict(zip(selected, row))
                    stats["dialogs"] = int(mapping.get("completed_dialogs") or 0)
                    stats["messages"] = int(mapping.get("messages_count") or 0)
                    stats["seconds"] = int(mapping.get("chat_time_seconds") or 0)
        if await _table_exists(conn, "reconnect_requests"):
            row = await (await conn.execute(
                "SELECT COUNT(*) FROM reconnect_requests WHERE status='accepted' "
                "AND (requester_id=? OR target_id=?)",
                (user_id, user_id),
            )).fetchone()
            stats["contacts"] = int(row[0] or 0) if row else 0

    minutes = stats["seconds"] // 60
    score = min(100, stats["dialogs"] * 8 + min(stats["messages"], 100) // 5 + min(minutes, 120) // 4)
    await _safe_edit(
        callback,
        "<b>⚡ Моя активность</b>\n\n"
        f"💬 Диалогов: <b>{stats['dialogs']}</b>\n"
        f"✉️ Сообщений: <b>{stats['messages']}</b>\n"
        f"⏱ Минут общения: <b>{minutes}</b>\n"
        f"🤝 Контактов: <b>{stats['contacts']}</b>\n\n"
        f"Индекс активности: <b>{score}/100</b>",
        InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎯 Задания", callback_data="engagement_missions")],
            [InlineKeyboardButton(text="⬅️ Профиль", callback_data="profile_refresh")],
        ]),
    )


@router.callback_query(F.data == "community_dialog_history")
async def profile_history_entry(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    items: list[tuple[int, str]] = []
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        if await _table_exists(conn, "recent_partners"):
            rows = await (await conn.execute(
                "SELECT partner_id,last_chat_at FROM recent_partners "
                "WHERE user_id=? ORDER BY last_chat_at DESC LIMIT 10",
                (user_id,),
            )).fetchall()
            items = [(int(row[0]), str(row[1] or "")) for row in rows]
    if items:
        lines = []
        for partner_id, timestamp in items:
            label = f"Собеседник #{abs(partner_id) % 10000:04d}"
            lines.append(f"• <b>{label}</b>\n  {timestamp[:16] or 'дата неизвестна'}")
        body = "\n\n".join(lines)
    else:
        body = "История пока пуста. Она появится после завершённых диалогов."
    await _safe_edit(
        callback,
        "<b>🕘 История знакомств</b>\n\n" + body
        + "\n\nСообщения и Telegram-профили не сохраняются.",
        _profile_back(),
    )


@router.callback_query(F.data == "community_connections")
async def profile_contacts_entry(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    total = 0
    enabled = True
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        if await _table_exists(conn, "reconnect_requests"):
            row = await (await conn.execute(
                "SELECT COUNT(*) FROM reconnect_requests WHERE status='accepted' "
                "AND (requester_id=? OR target_id=?)",
                (user_id, user_id),
            )).fetchone()
            total = int(row[0] or 0) if row else 0
        if await _table_exists(conn, "community_settings"):
            row = await (await conn.execute(
                "SELECT reconnect_allowed FROM community_settings WHERE user_id=?",
                (user_id,),
            )).fetchone()
            if row is not None:
                enabled = bool(row[0])
    await _safe_edit(
        callback,
        "<b>🤝 Мои контакты</b>\n\n"
        f"Взаимных контактов: <b>{total}</b>\n"
        f"Новые сохранения: <b>{'разрешены' if enabled else 'запрещены'}</b>\n\n"
        "Контакт появляется только после взаимного согласия.",
        InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Список", callback_data="community_contacts_list")],
            [InlineKeyboardButton(
                text="🤝 Сохранение: вкл" if enabled else "🚫 Сохранение: выкл",
                callback_data="community_reconnect_toggle",
            )],
            [InlineKeyboardButton(text="⬅️ Профиль", callback_data="profile_refresh")],
        ]),
    )

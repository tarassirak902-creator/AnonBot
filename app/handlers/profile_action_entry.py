from __future__ import annotations

import aiosqlite
from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.database.repository import DB_PATH
from app.services.engagement_service import claim_daily_mission, load_daily_missions
from .shared import router


async def _table_exists(conn: aiosqlite.Connection, name: str) -> bool:
    row = await (await conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    )).fetchone()
    return row is not None


async def _safe_edit(callback: CallbackQuery, text: str, keyboard: InlineKeyboardMarkup) -> None:
    await callback.answer()
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)


def _profile_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Профиль", callback_data="profile_refresh")],
    ])


@router.callback_query(F.data == "profile_hub_activity")
async def profile_hub_activity(callback: CallbackQuery) -> None:
    await _safe_edit(
        callback,
        "<b>⚡ Активность</b>\n\nСтатистика, история общения и достижения в одном разделе.",
        InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="user_activity_center")],
            [InlineKeyboardButton(text="🕘 История", callback_data="community_dialog_history")],
            [InlineKeyboardButton(text="🏆 Достижения", callback_data="profile_achievements")],
            [InlineKeyboardButton(text="⬅️ Профиль", callback_data="profile_refresh")],
        ]),
    )


@router.callback_query(F.data == "profile_hub_rewards")
async def profile_hub_rewards(callback: CallbackQuery) -> None:
    await _safe_edit(
        callback,
        "<b>🎁 Награды</b>\n\nЕжедневные задания, бонусы и события собраны здесь.",
        InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎯 Задания", callback_data="engagement_missions")],
            [InlineKeyboardButton(text="🎁 Ежедневный бонус", callback_data="profile_daily_reward")],
            [InlineKeyboardButton(text="🎪 Событие недели", callback_data="weekly_event")],
            [InlineKeyboardButton(text="⬅️ Профиль", callback_data="profile_refresh")],
        ]),
    )


@router.callback_query(F.data == "profile_hub_social")
async def profile_hub_social(callback: CallbackQuery) -> None:
    await _safe_edit(
        callback,
        "<b>🤝 Социальное</b>\n\nКонтакты, приглашения и сохранённые связи.",
        InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🤝 Контакты", callback_data="community_connections")],
            [InlineKeyboardButton(text="👥 Приглашения", callback_data="profile_invited_users")],
            [InlineKeyboardButton(text="🔍 Раскрытия", callback_data="profile_my_revealed")],
            [InlineKeyboardButton(text="⬅️ Профиль", callback_data="profile_refresh")],
        ]),
    )


@router.callback_query(F.data == "profile_hub_premium")
async def profile_hub_premium(callback: CallbackQuery) -> None:
    await _safe_edit(
        callback,
        "<b>👑 Премиум</b>\n\nБаланс, VIP и дополнительные возможности аккаунта.",
        InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Баланс", callback_data="profile_withdraw")],
            [InlineKeyboardButton(text="👑 VIP", callback_data="buy_vip_sub")],
            [InlineKeyboardButton(text="🎁 Подарки", callback_data="profile_my_received_gifts")],
            [InlineKeyboardButton(text="⬅️ Профиль", callback_data="profile_refresh")],
        ]),
    )


async def _render_missions(callback: CallbackQuery) -> None:
    missions = await load_daily_missions(callback.from_user.id)
    lines: list[str] = []
    rows: list[list[InlineKeyboardButton]] = []
    for item in missions:
        code = str(item["code"])
        reward = int(item["reward"])
        if item["claimed"]:
            status = "✅ получено"
        elif item["completed"]:
            status = "🎁 готово"
            rows.append([InlineKeyboardButton(
                text=f"🎁 Забрать {reward} ⭐",
                callback_data=f"engagement_mission_claim:{code}",
            )])
        else:
            status = f"⏳ {item['progress']}/{item['target']}"
        lines.append(f"• <b>{item['title']}</b> — {status} · {reward} ⭐")
    rows.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="engagement_missions")])
    rows.append([InlineKeyboardButton(text="⬅️ Награды", callback_data="profile_hub_rewards")])
    await _safe_edit(
        callback,
        "<b>🎯 Задания на сегодня</b>\n\n" + "\n".join(lines)
        + "\n\nПрогресс и выдача награды используют один источник данных.",
        InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data == "engagement_missions")
async def profile_missions_entry(callback: CallbackQuery) -> None:
    await _render_missions(callback)


@router.callback_query(F.data.startswith("engagement_mission_claim:"))
async def profile_mission_claim(callback: CallbackQuery) -> None:
    code = callback.data.split(":", 1)[1]
    result = await claim_daily_mission(callback.from_user.id, code)
    status = result["status"]
    if status == "ok":
        await callback.answer(f"Начислено {result['reward']} ⭐", show_alert=True)
    elif status == "incomplete":
        await callback.answer("Задание ещё не выполнено", show_alert=True)
    elif status == "claimed":
        await callback.answer("Награда уже получена")
    else:
        await callback.answer("Задание обновилось. Открой список ещё раз.", show_alert=True)
    await _render_missions(callback)


@router.callback_query(F.data == "user_activity_center")
async def profile_activity_entry(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    stats = {"dialogs": 0, "messages": 0, "seconds": 0, "contacts": 0}
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        if await _table_exists(conn, "users"):
            columns = {row[1] for row in await (await conn.execute("PRAGMA table_info(users)")).fetchall()}
            selected = [c for c in ("completed_dialogs", "messages_count", "chat_time_seconds") if c in columns]
            if selected:
                row = await (await conn.execute(
                    f"SELECT {','.join(selected)} FROM users WHERE user_id=?", (user_id,),
                )).fetchone()
                if row:
                    mapping = dict(zip(selected, row))
                    stats["dialogs"] = int(mapping.get("completed_dialogs") or 0)
                    stats["messages"] = int(mapping.get("messages_count") or 0)
                    stats["seconds"] = int(mapping.get("chat_time_seconds") or 0)
        if await _table_exists(conn, "reconnect_requests"):
            row = await (await conn.execute(
                "SELECT COUNT(*) FROM reconnect_requests WHERE status='accepted' AND (requester_id=? OR target_id=?)",
                (user_id, user_id),
            )).fetchone()
            stats["contacts"] = int(row[0] or 0) if row else 0
    minutes = stats["seconds"] // 60
    score = min(100, stats["dialogs"] * 8 + min(stats["messages"], 100) // 5 + min(minutes, 120) // 4)
    await _safe_edit(
        callback,
        "<b>📊 Моя статистика</b>\n\n"
        f"💬 Диалогов: <b>{stats['dialogs']}</b>\n"
        f"✉️ Сообщений: <b>{stats['messages']}</b>\n"
        f"⏱ Минут общения: <b>{minutes}</b>\n"
        f"🤝 Контактов: <b>{stats['contacts']}</b>\n\n"
        f"Индекс активности: <b>{score}/100</b>",
        InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Активность", callback_data="profile_hub_activity")],
        ]),
    )


@router.callback_query(F.data == "community_dialog_history")
async def profile_history_entry(callback: CallbackQuery) -> None:
    items: list[tuple[int, str]] = []
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        if await _table_exists(conn, "recent_partners"):
            rows = await (await conn.execute(
                "SELECT partner_id,last_chat_at FROM recent_partners WHERE user_id=? ORDER BY last_chat_at DESC LIMIT 10",
                (callback.from_user.id,),
            )).fetchall()
            items = [(int(row[0]), str(row[1] or "")) for row in rows]
    body = "История пока пуста."
    if items:
        body = "\n\n".join(
            f"• <b>Собеседник #{abs(partner_id) % 10000:04d}</b>\n  {timestamp[:16] or 'дата неизвестна'}"
            for partner_id, timestamp in items
        )
    await _safe_edit(
        callback,
        "<b>🕘 История знакомств</b>\n\n" + body + "\n\nСообщения и Telegram-профили не сохраняются.",
        InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Активность", callback_data="profile_hub_activity")],
        ]),
    )


@router.callback_query(F.data == "community_connections")
async def profile_contacts_entry(callback: CallbackQuery) -> None:
    total = 0
    enabled = True
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        if await _table_exists(conn, "reconnect_requests"):
            row = await (await conn.execute(
                "SELECT COUNT(*) FROM reconnect_requests WHERE status='accepted' AND (requester_id=? OR target_id=?)",
                (callback.from_user.id, callback.from_user.id),
            )).fetchone()
            total = int(row[0] or 0) if row else 0
        if await _table_exists(conn, "community_settings"):
            row = await (await conn.execute(
                "SELECT reconnect_allowed FROM community_settings WHERE user_id=?", (callback.from_user.id,),
            )).fetchone()
            if row is not None:
                enabled = bool(row[0])
    await _safe_edit(
        callback,
        "<b>🤝 Мои контакты</b>\n\n"
        f"Взаимных контактов: <b>{total}</b>\n"
        f"Новые сохранения: <b>{'разрешены' if enabled else 'запрещены'}</b>",
        InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Список", callback_data="community_contacts_list")],
            [InlineKeyboardButton(text="⬅️ Социальное", callback_data="profile_hub_social")],
        ]),
    )

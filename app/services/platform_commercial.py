from __future__ import annotations

import aiosqlite

from app.database.repository import DB_PATH


async def _table_exists(conn: aiosqlite.Connection, table: str) -> bool:
    row = await (await conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )).fetchone()
    return row is not None


async def load_user_commercial_status(user_id: int) -> dict[str, int | str | bool]:
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        conn.row_factory = aiosqlite.Row
        user = await (await conn.execute(
            "SELECT stars_balance,is_vip,completed_dialogs,messages_count,chat_time_seconds "
            "FROM users WHERE user_id=?", (user_id,)
        )).fetchone()
        if not user:
            return {"level": 1, "xp": 0, "next_xp": 100, "progress": 0, "tier": "Новичок", "stars": 0, "vip": False, "dialogs": 0}

        contacts = 0
        if await _table_exists(conn, "user_contacts"):
            row = await (await conn.execute(
                "SELECT COUNT(*) FROM user_contacts WHERE user_id=?", (user_id,)
            )).fetchone()
            contacts = int(row[0] or 0)

        dialogs = int(user["completed_dialogs"] or 0)
        messages = int(user["messages_count"] or 0)
        minutes = int(user["chat_time_seconds"] or 0) // 60
        xp = dialogs * 25 + min(messages, 5000) // 5 + min(minutes, 5000) // 2 + contacts * 20
        level = max(1, int((xp / 100) ** 0.5) + 1)
        level_floor = (level - 1) ** 2 * 100
        next_xp = level ** 2 * 100
        progress = max(0, min(100, int((xp - level_floor) * 100 / max(1, next_xp - level_floor))))
        tier = "Новичок" if level < 3 else "Активный" if level < 6 else "Опытный" if level < 10 else "Легенда"
        return {
            "level": level,
            "xp": xp,
            "next_xp": next_xp,
            "progress": progress,
            "tier": tier,
            "stars": int(user["stars_balance"] or 0),
            "vip": bool(user["is_vip"]),
            "dialogs": dialogs,
            "contacts": contacts,
        }


async def load_business_metrics() -> dict[str, int]:
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        async def scalar(sql: str, params=()) -> int:
            try:
                row = await (await conn.execute(sql, params)).fetchone()
                return int((row[0] if row else 0) or 0)
            except Exception:
                return 0

        return {
            "users": await scalar("SELECT COUNT(*) FROM users"),
            "new_24h": await scalar("SELECT COUNT(*) FROM users WHERE datetime(joined_date)>=datetime('now','-1 day')"),
            "active_24h": await scalar("SELECT COUNT(*) FROM users WHERE datetime(last_activity)>=datetime('now','-1 day')"),
            "vip": await scalar("SELECT COUNT(*) FROM users WHERE is_vip=1"),
            "stars_revenue": await scalar("SELECT COALESCE(SUM(price_stars),0) FROM purchases"),
            "purchases_24h": await scalar("SELECT COUNT(*) FROM purchases WHERE datetime(timestamp)>=datetime('now','-1 day')"),
            "queue": await scalar("SELECT COUNT(*) FROM queues"),
            "active_pairs": await scalar("SELECT COUNT(*)/2 FROM active_chats"),
            "complaints_24h": await scalar("SELECT COUNT(*) FROM complaints WHERE datetime(timestamp)>=datetime('now','-1 day')"),
        }

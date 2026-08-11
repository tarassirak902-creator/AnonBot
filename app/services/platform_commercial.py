from __future__ import annotations

import aiosqlite

from app.database.repository import DB_PATH
from app.database.platform_progress_repository import get_progress_profile


async def _table_exists(conn: aiosqlite.Connection, table: str) -> bool:
    row = await (await conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )).fetchone()
    return row is not None


def _tier_for_level(level: int) -> str:
    if level < 3:
        return "Новичок"
    if level < 6:
        return "Активный"
    if level < 10:
        return "Опытный"
    return "Легенда"


async def load_user_commercial_status(user_id: int) -> dict[str, int | str | bool]:
    """Build the commercial profile from the same XP ledger as Progress.

    Previously this screen derived a second synthetic XP value from message and
    chat counters, so users could see two different levels in adjacent screens.
    The canonical ``account_progress`` ledger is now the single source of truth.
    """
    progress = await get_progress_profile(user_id)
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        conn.row_factory = aiosqlite.Row
        user = await (await conn.execute(
            "SELECT stars_balance,is_vip,completed_dialogs FROM users WHERE user_id=?",
            (user_id,),
        )).fetchone()
        if not user:
            return {
                "level": progress.level,
                "xp": progress.xp,
                "next_xp": progress.next_level_xp,
                "progress": 0,
                "tier": _tier_for_level(progress.level),
                "stars": 0,
                "vip": False,
                "dialogs": 0,
                "contacts": 0,
            }

        contacts = 0
        if await _table_exists(conn, "reconnect_requests"):
            row = await (await conn.execute(
                """SELECT COUNT(DISTINCT CASE
                       WHEN requester_id=? THEN target_id ELSE requester_id END)
                   FROM reconnect_requests
                  WHERE status='accepted' AND (requester_id=? OR target_id=?)""",
                (user_id, user_id, user_id),
            )).fetchone()
            contacts = int(row[0] or 0) if row else 0

        required = max(1, int(progress.next_level_xp))
        current = max(0, int(progress.current_level_xp))
        percent = max(0, min(100, int(current * 100 / required)))
        return {
            "level": progress.level,
            "xp": progress.xp,
            "next_xp": progress.next_level_xp,
            "progress": percent,
            "tier": _tier_for_level(progress.level),
            "stars": int(user["stars_balance"] or 0),
            "vip": bool(user["is_vip"]),
            "dialogs": int(user["completed_dialogs"] or 0),
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

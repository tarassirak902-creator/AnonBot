from __future__ import annotations

from datetime import datetime, timedelta

import aiosqlite

from app.database.repository import DB_PATH


async def _table_exists(conn: aiosqlite.Connection, table: str) -> bool:
    row = await (await conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )).fetchone()
    return row is not None


async def _columns(conn: aiosqlite.Connection, table: str) -> set[str]:
    if not await _table_exists(conn, table):
        return set()
    rows = await (await conn.execute(f"PRAGMA table_info({table})")).fetchall()
    return {str(row[1]) for row in rows}


async def _count(conn: aiosqlite.Connection, sql: str, params: tuple = ()) -> int:
    try:
        row = await (await conn.execute(sql, params)).fetchone()
    except aiosqlite.Error:
        return 0
    return int(row[0] or 0) if row else 0


async def load_admin_operational_snapshot() -> dict[str, int]:
    """Return a dashboard snapshot even when optional legacy tables differ."""
    now = datetime.now()
    day_ago = (now - timedelta(days=1)).isoformat()
    week_ago = (now - timedelta(days=7)).isoformat()
    result = {
        "queue": 0,
        "active_chats": 0,
        "users_24h": 0,
        "users_7d": 0,
        "complaints": 0,
        "pending_reconnects": 0,
        "mutual_contacts": 0,
        "ratings_24h": 0,
        "negative_ratings_24h": 0,
    }
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        result["queue"] = await _count(conn, "SELECT COUNT(*) FROM queues")
        result["active_chats"] = await _count(conn, "SELECT COUNT(*) FROM active_chats")

        user_cols = await _columns(conn, "users")
        created = next(
            (
                name
                for name in ("joined_date", "created_at", "join_date", "registered_at")
                if name in user_cols
            ),
            None,
        )
        if created:
            result["users_24h"] = await _count(
                conn,
                f"SELECT COUNT(*) FROM users WHERE datetime({created})>=datetime(?)",
                (day_ago,),
            )
            result["users_7d"] = await _count(
                conn,
                f"SELECT COUNT(*) FROM users WHERE datetime({created})>=datetime(?)",
                (week_ago,),
            )

        complaint_cols = await _columns(conn, "complaints")
        if complaint_cols:
            result["complaints"] = await _count(conn, "SELECT COUNT(*) FROM complaints")
        elif "complaints_sent" in user_cols:
            result["complaints"] = await _count(
                conn, "SELECT COALESCE(SUM(complaints_sent),0) FROM users"
            )

        if await _table_exists(conn, "reconnect_requests"):
            result["pending_reconnects"] = await _count(
                conn, "SELECT COUNT(*) FROM reconnect_requests WHERE status='pending'"
            )
            result["mutual_contacts"] = await _count(
                conn, "SELECT COUNT(*) FROM reconnect_requests WHERE status='accepted'"
            )

        rating_cols = await _columns(conn, "chat_ratings")
        if {"created_at", "score"}.issubset(rating_cols):
            result["ratings_24h"] = await _count(
                conn, "SELECT COUNT(*) FROM chat_ratings WHERE created_at>=?", (day_ago,)
            )
            result["negative_ratings_24h"] = await _count(
                conn, "SELECT COUNT(*) FROM chat_ratings WHERE created_at>=? AND score<0", (day_ago,)
            )
    return result


async def load_recent_anonymous_contacts(user_id: int, limit: int = 8) -> list[dict[str, object]]:
    """Return mutual contacts without exposing Telegram identity."""
    items: list[dict[str, object]] = []
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        if not await _table_exists(conn, "reconnect_requests"):
            return items
        rows = await (await conn.execute(
            """SELECT CASE WHEN requester_id=? THEN target_id ELSE requester_id END AS contact_id,
                      MAX(updated_at) AS connected_at
                 FROM reconnect_requests
                WHERE status='accepted' AND (requester_id=? OR target_id=?)
                GROUP BY contact_id
                ORDER BY connected_at DESC
                LIMIT ?""",
            (user_id, user_id, user_id, max(1, min(limit, 20))),
        )).fetchall()
    for index, row in enumerate(rows, start=1):
        items.append({
            "contact_id": int(row[0]),
            "label": f"Аноним #{index}",
            "connected_at": str(row[1] or ""),
        })
    return items


async def remove_anonymous_contact(user_id: int, contact_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        if not await _table_exists(conn, "reconnect_requests"):
            return False
        cursor = await conn.execute(
            "DELETE FROM reconnect_requests WHERE "
            "(requester_id=? AND target_id=?) OR (requester_id=? AND target_id=?)",
            (user_id, contact_id, contact_id, user_id),
        )
        await conn.commit()
        return bool(cursor.rowcount)

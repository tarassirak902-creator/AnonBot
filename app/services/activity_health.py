from __future__ import annotations

from datetime import datetime, timedelta

import aiosqlite

from app.database.repository import DB_PATH


async def _table_exists(conn: aiosqlite.Connection, table: str) -> bool:
    row = await (
        await conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
    ).fetchone()
    return row is not None


async def _columns(conn: aiosqlite.Connection, table: str) -> set[str]:
    if not await _table_exists(conn, table):
        return set()
    rows = await (await conn.execute(f"PRAGMA table_info({table})")).fetchall()
    return {str(row[1]) for row in rows}


async def load_user_weekly_activity(user_id: int) -> dict[str, int]:
    result = {
        "dialogs": 0,
        "messages": 0,
        "chat_minutes": 0,
        "questions_sent": 0,
        "questions_answered": 0,
        "ratings_given": 0,
        "mission_rewards": 0,
        "contacts": 0,
        "active_days": 0,
    }
    since = (datetime.now() - timedelta(days=7)).isoformat()
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        user_cols = await _columns(conn, "users")
        if user_cols:
            selected = []
            for name in ("completed_dialogs", "messages_count", "chat_time_seconds"):
                selected.append(name if name in user_cols else "0")
            row = await (
                await conn.execute(
                    f"SELECT {','.join(selected)} FROM users WHERE user_id=?",
                    (user_id,),
                )
            ).fetchone()
            if row:
                result["dialogs"] = int(row[0] or 0)
                result["messages"] = int(row[1] or 0)
                result["chat_minutes"] = int((row[2] or 0) // 60)

        q_cols = await _columns(conn, "anonymous_questions")
        if q_cols:
            created = "created_at" if "created_at" in q_cols else "''"
            answered = "answered_at" if "answered_at" in q_cols else "NULL"
            row = await (
                await conn.execute(
                    f"SELECT "
                    f"SUM(CASE WHEN sender_id=? AND {created}>=? THEN 1 ELSE 0 END),"
                    f"SUM(CASE WHEN receiver_id=? AND {answered}>=? THEN 1 ELSE 0 END) "
                    f"FROM anonymous_questions",
                    (user_id, since, user_id, since),
                )
            ).fetchone()
            if row:
                result["questions_sent"] = int(row[0] or 0)
                result["questions_answered"] = int(row[1] or 0)

        rating_table = "partner_ratings" if await _table_exists(conn, "partner_ratings") else (
            "user_ratings" if await _table_exists(conn, "user_ratings") else None
        )
        if rating_table:
            cols = await _columns(conn, rating_table)
            author = next((c for c in ("rater_id", "from_user_id", "user_id") if c in cols), None)
            stamp = next((c for c in ("created_at", "timestamp", "rated_at") if c in cols), None)
            if author:
                query = f"SELECT COUNT(*) FROM {rating_table} WHERE {author}=?"
                params: tuple[object, ...] = (user_id,)
                if stamp:
                    query += f" AND {stamp}>=?"
                    params = (user_id, since)
                row = await (await conn.execute(query, params)).fetchone()
                result["ratings_given"] = int(row[0] or 0) if row else 0

        if await _table_exists(conn, "daily_mission_claims"):
            cols = await _columns(conn, "daily_mission_claims")
            stamp = next((c for c in ("claimed_at", "created_at") if c in cols), None)
            query = "SELECT COUNT(*) FROM daily_mission_claims WHERE user_id=?"
            params = (user_id,)
            if stamp:
                query += f" AND {stamp}>=?"
                params = (user_id, since)
            row = await (await conn.execute(query, params)).fetchone()
            result["mission_rewards"] = int(row[0] or 0) if row else 0

        if await _table_exists(conn, "reconnect_requests"):
            row = await (
                await conn.execute(
                    "SELECT COUNT(DISTINCT CASE WHEN requester_id=? THEN target_id ELSE requester_id END) "
                    "FROM reconnect_requests WHERE status='accepted' AND (requester_id=? OR target_id=?)",
                    (user_id, user_id, user_id),
                )
            ).fetchone()
            result["contacts"] = int(row[0] or 0) if row else 0

        if await _table_exists(conn, "logs"):
            cols = await _columns(conn, "logs")
            stamp = "timestamp" if "timestamp" in cols else None
            if stamp:
                rows = await (
                    await conn.execute(
                        f"SELECT COUNT(DISTINCT substr({stamp},1,10)) FROM logs WHERE user_id=? AND {stamp}>=?",
                        (user_id, since),
                    )
                ).fetchone()
                result["active_days"] = int(rows[0] or 0) if rows else 0
    return result


async def load_platform_health() -> dict[str, int]:
    result = {
        "queue_total": 0,
        "queue_stale": 0,
        "active_rows": 0,
        "active_pairs": 0,
        "one_sided_chats": 0,
        "stale_chats": 0,
        "route_errors_24h": 0,
        "unreviewed_complaints": 0,
    }
    now = datetime.now()
    queue_cutoff = (now - timedelta(minutes=10)).isoformat()
    chat_cutoff = (now - timedelta(hours=6)).isoformat()
    day_cutoff = (now - timedelta(hours=24)).isoformat()
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        if await _table_exists(conn, "queues"):
            cols = await _columns(conn, "queues")
            row = await (await conn.execute("SELECT COUNT(*) FROM queues")).fetchone()
            result["queue_total"] = int(row[0] or 0) if row else 0
            if "created_at" in cols:
                row = await (
                    await conn.execute(
                        "SELECT COUNT(*) FROM queues WHERE created_at<?",
                        (queue_cutoff,),
                    )
                ).fetchone()
                result["queue_stale"] = int(row[0] or 0) if row else 0

        if await _table_exists(conn, "active_chats"):
            cols = await _columns(conn, "active_chats")
            row = await (await conn.execute("SELECT COUNT(*) FROM active_chats")).fetchone()
            result["active_rows"] = int(row[0] or 0) if row else 0
            result["active_pairs"] = result["active_rows"] // 2
            row = await (
                await conn.execute(
                    "SELECT COUNT(*) FROM active_chats a "
                    "LEFT JOIN active_chats b ON b.user_id=a.partner_id AND b.partner_id=a.user_id "
                    "WHERE b.user_id IS NULL"
                )
            ).fetchone()
            result["one_sided_chats"] = int(row[0] or 0) if row else 0
            if "created_at" in cols:
                row = await (
                    await conn.execute(
                        "SELECT COUNT(*) FROM active_chats WHERE created_at<?",
                        (chat_cutoff,),
                    )
                ).fetchone()
                result["stale_chats"] = int(row[0] or 0) if row else 0

        if await _table_exists(conn, "logs"):
            cols = await _columns(conn, "logs")
            if {"action", "timestamp"}.issubset(cols):
                row = await (
                    await conn.execute(
                        "SELECT COUNT(*) FROM logs WHERE timestamp>=? AND "
                        "(lower(action) LIKE '%error%' OR lower(action) LIKE '%exception%' OR lower(action) LIKE '%failed%')",
                        (day_cutoff,),
                    )
                ).fetchone()
                result["route_errors_24h"] = int(row[0] or 0) if row else 0

        if await _table_exists(conn, "complaints"):
            if await _table_exists(conn, "complaint_reviews"):
                row = await (
                    await conn.execute(
                        "SELECT COUNT(*) FROM complaints c LEFT JOIN complaint_reviews r ON r.complaint_id=c.id "
                        "WHERE r.complaint_id IS NULL"
                    )
                ).fetchone()
            else:
                row = await (await conn.execute("SELECT COUNT(*) FROM complaints")).fetchone()
            result["unreviewed_complaints"] = int(row[0] or 0) if row else 0
    return result

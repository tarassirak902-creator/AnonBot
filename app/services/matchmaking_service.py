from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import aiosqlite

from app.database.repository import DB_PATH


@dataclass(frozen=True)
class MatchResult:
    user_id: int
    partner_id: int | None
    queued: bool
    recovered_rows: int = 0


async def _table_exists(conn: aiosqlite.Connection, table: str) -> bool:
    row = await (
        await conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
    ).fetchone()
    return row is not None


async def _recent_partner_ids(
    conn: aiosqlite.Connection,
    user_id: int,
    limit: int = 3,
) -> set[int]:
    if not await _table_exists(conn, "recent_partners"):
        return set()
    columns = await (await conn.execute("PRAGMA table_info(recent_partners)")).fetchall()
    names = {str(row[1]) for row in columns}
    if not {"user_id", "partner_id"}.issubset(names):
        return set()
    order_column = "last_chat_at" if "last_chat_at" in names else "rowid"
    rows = await (
        await conn.execute(
            f"SELECT partner_id FROM recent_partners WHERE user_id=? "
            f"ORDER BY {order_column} DESC LIMIT ?",
            (user_id, limit),
        )
    ).fetchall()
    return {int(row[0]) for row in rows if row and row[0] is not None}


async def _repair_active_chats(conn: aiosqlite.Connection) -> int:
    """Remove self-links, missing partners and non-symmetric chat rows."""
    if not await _table_exists(conn, "active_chats"):
        return 0
    cursor = await conn.execute(
        "DELETE FROM active_chats "
        "WHERE user_id=partner_id "
        "OR NOT EXISTS ("
        "  SELECT 1 FROM active_chats peer "
        "  WHERE peer.user_id=active_chats.partner_id "
        "    AND peer.partner_id=active_chats.user_id"
        ")"
    )
    return max(0, int(cursor.rowcount or 0))


async def recover_matchmaking_state(
    *,
    stale_queue_after: timedelta = timedelta(hours=6),
) -> int:
    cutoff = (datetime.now(timezone.utc) - stale_queue_after).isoformat()
    async with aiosqlite.connect(DB_PATH, timeout=15) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("BEGIN IMMEDIATE")
        repaired = await _repair_active_chats(conn)
        if await _table_exists(conn, "queues"):
            cursor = await conn.execute(
                "DELETE FROM queues WHERE created_at IS NOT NULL AND created_at<?",
                (cutoff,),
            )
            repaired += max(0, int(cursor.rowcount or 0))
            cursor = await conn.execute(
                "DELETE FROM queues WHERE user_id IN (SELECT user_id FROM active_chats)"
            )
            repaired += max(0, int(cursor.rowcount or 0))
        await conn.commit()
        return repaired


async def enqueue_or_match(user_id: int) -> MatchResult:
    """Atomically enqueue a user or connect them to the longest-waiting peer."""
    async with aiosqlite.connect(DB_PATH, timeout=15) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("BEGIN IMMEDIATE")
        repaired = await _repair_active_chats(conn)

        current = await (
            await conn.execute(
                "SELECT partner_id FROM active_chats WHERE user_id=?",
                (user_id,),
            )
        ).fetchone()
        if current:
            await conn.execute("DELETE FROM queues WHERE user_id=?", (user_id,))
            await conn.commit()
            return MatchResult(user_id, int(current[0]), False, repaired)

        await conn.execute(
            "INSERT INTO queues(user_id,created_at) VALUES (?,CURRENT_TIMESTAMP) "
            "ON CONFLICT(user_id) DO NOTHING",
            (user_id,),
        )

        excluded = await _recent_partner_ids(conn, user_id)
        params: list[int] = [user_id]
        exclusion_sql = ""
        if excluded:
            placeholders = ",".join("?" for _ in excluded)
            exclusion_sql = f" AND q.user_id NOT IN ({placeholders})"
            params.extend(sorted(excluded))

        candidate = await (
            await conn.execute(
                "SELECT q.user_id FROM queues q "
                "LEFT JOIN active_chats a ON a.user_id=q.user_id "
                "WHERE q.user_id<>? AND a.user_id IS NULL"
                + exclusion_sql
                + " ORDER BY q.created_at ASC, q.user_id ASC LIMIT 1",
                tuple(params),
            )
        ).fetchone()

        if not candidate and excluded:
            candidate = await (
                await conn.execute(
                    "SELECT q.user_id FROM queues q "
                    "LEFT JOIN active_chats a ON a.user_id=q.user_id "
                    "WHERE q.user_id<>? AND a.user_id IS NULL "
                    "ORDER BY q.created_at ASC, q.user_id ASC LIMIT 1",
                    (user_id,),
                )
            ).fetchone()

        if not candidate:
            await conn.commit()
            return MatchResult(user_id, None, True, repaired)

        partner_id = int(candidate[0])
        await conn.execute(
            "DELETE FROM queues WHERE user_id IN (?,?)",
            (user_id, partner_id),
        )
        await conn.execute(
            "DELETE FROM active_chats WHERE user_id IN (?,?) OR partner_id IN (?,?)",
            (user_id, partner_id, user_id, partner_id),
        )
        await conn.executemany(
            "INSERT INTO active_chats(user_id,partner_id,created_at) "
            "VALUES (?,?,CURRENT_TIMESTAMP)",
            ((user_id, partner_id), (partner_id, user_id)),
        )
        await conn.commit()
        return MatchResult(user_id, partner_id, False, repaired)


async def leave_queue(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        cursor = await conn.execute("DELETE FROM queues WHERE user_id=?", (user_id,))
        await conn.commit()
        return bool(cursor.rowcount)

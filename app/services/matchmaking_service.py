from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import aiosqlite

from app.database.matchmaking_repository import try_match_user
from app.database.repository import DB_PATH


_MATCH_LOCK = asyncio.Lock()


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


async def _repair_active_chats(conn: aiosqlite.Connection) -> int:
    """Remove invalid rows without disturbing users that remain in a valid pair."""
    if not await _table_exists(conn, "active_chats"):
        return 0

    invalid_rows = await (
        await conn.execute(
            """
            SELECT user_id, partner_id
            FROM active_chats a
            WHERE user_id=partner_id
               OR NOT EXISTS (
                    SELECT 1 FROM active_chats peer
                    WHERE peer.user_id=a.partner_id
                      AND peer.partner_id=a.user_id
               )
            """
        )
    ).fetchall()
    if not invalid_rows:
        return 0

    affected_ids = {
        int(value)
        for row in invalid_rows
        for value in row
        if value is not None and int(value) > 0
    }
    cursor = await conn.execute(
        "DELETE FROM active_chats "
        "WHERE user_id=partner_id "
        "OR NOT EXISTS ("
        "  SELECT 1 FROM active_chats peer "
        "  WHERE peer.user_id=active_chats.partner_id "
        "    AND peer.partner_id=active_chats.user_id"
        ")"
    )
    removed = max(0, int(cursor.rowcount or 0))

    if affected_ids:
        placeholders = ",".join("?" for _ in affected_ids)
        params = tuple(sorted(affected_ids))
        # A corrupt extra row may point at somebody who is still in a different,
        # fully reciprocal pair. Only users left without any active row after the
        # deletion have stale session markers and queue entries cleared.
        await conn.execute(
            f"""
            UPDATE users
               SET current_chat_start=NULL
             WHERE user_id IN ({placeholders})
               AND NOT EXISTS (
                    SELECT 1 FROM active_chats a WHERE a.user_id=users.user_id
               )
            """,
            params,
        )
        await conn.execute(
            f"""
            DELETE FROM queues
             WHERE user_id IN ({placeholders})
               AND NOT EXISTS (
                    SELECT 1 FROM active_chats a WHERE a.user_id=queues.user_id
               )
            """,
            params,
        )

    return removed


async def recover_matchmaking_state(
    *,
    stale_queue_after: timedelta = timedelta(hours=6),
) -> int:
    """Repair transient matchmaking state without touching durable user history."""
    cutoff = (datetime.now(timezone.utc) - stale_queue_after).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    async with aiosqlite.connect(DB_PATH, timeout=15) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("BEGIN IMMEDIATE")
        repaired = await _repair_active_chats(conn)
        if await _table_exists(conn, "queues"):
            cursor = await conn.execute(
                "DELETE FROM queues WHERE created_at IS NOT NULL AND datetime(created_at)<datetime(?)",
                (cutoff,),
            )
            repaired += max(0, int(cursor.rowcount or 0))
            cursor = await conn.execute(
                "DELETE FROM queues WHERE user_id IN ("
                "SELECT user_id FROM active_chats UNION SELECT partner_id FROM active_chats"
                ")"
            )
            repaired += max(0, int(cursor.rowcount or 0))
        await conn.commit()
        return repaired


async def enqueue_or_match(user_id: int) -> MatchResult:
    """Repair and match as one process-serialized operation.

    SQLite already serializes the repository transaction. The process lock also
    prevents a second coroutine from running recovery between another request's
    recovery and canonical match transaction.
    """
    async with _MATCH_LOCK:
        recovered = await recover_matchmaking_state()
        partner_id = await try_match_user(user_id)
        if partner_id is not None:
            return MatchResult(user_id, int(partner_id), False, recovered)

        async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
            row = await (
                await conn.execute(
                    "SELECT partner_id FROM active_chats WHERE user_id=?",
                    (user_id,),
                )
            ).fetchone()
            if row:
                return MatchResult(user_id, int(row[0]), False, recovered)
            queued = await (
                await conn.execute("SELECT 1 FROM queues WHERE user_id=?", (user_id,))
            ).fetchone()
        return MatchResult(user_id, None, bool(queued), recovered)


async def leave_queue(user_id: int) -> bool:
    async with _MATCH_LOCK:
        async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
            cursor = await conn.execute("DELETE FROM queues WHERE user_id=?", (user_id,))
            await conn.commit()
            return bool(cursor.rowcount)


async def matchmaking_health() -> dict[str, int]:
    """Return operational counters for admin diagnostics."""
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        queue = await (await conn.execute("SELECT COUNT(*) FROM queues")).fetchone()
        oldest = await (
            await conn.execute(
                "SELECT COALESCE(MAX(0, CAST((julianday('now')-julianday(MIN(created_at)))*86400 AS INTEGER)),0) "
                "FROM queues"
            )
        ).fetchone()
        broken = await (
            await conn.execute(
                "SELECT COUNT(*) FROM active_chats a "
                "WHERE NOT EXISTS ("
                "SELECT 1 FROM active_chats b "
                "WHERE b.user_id=a.partner_id AND b.partner_id=a.user_id"
                ")"
            )
        ).fetchone()
        self_links = await (
            await conn.execute(
                "SELECT COUNT(*) FROM active_chats WHERE user_id=partner_id"
            )
        ).fetchone()
    return {
        "queue": int(queue[0] or 0) if queue else 0,
        "oldest_wait_seconds": int(oldest[0] or 0) if oldest else 0,
        "broken_links": int(broken[0] or 0) if broken else 0,
        "self_links": int(self_links[0] or 0) if self_links else 0,
    }

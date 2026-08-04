from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import aiosqlite

from app.database.matchmaking_repository import try_match_user
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


async def _repair_active_chats(conn: aiosqlite.Connection) -> int:
    """Remove self-links, missing peers and non-symmetric chat rows."""
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
    """Repair transient matchmaking state without touching user history."""
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
                "DELETE FROM queues WHERE user_id IN ("
                "SELECT user_id FROM active_chats UNION SELECT partner_id FROM active_chats"
                ")"
            )
            repaired += max(0, int(cursor.rowcount or 0))
        await conn.commit()
        return repaired


async def enqueue_or_match(user_id: int) -> MatchResult:
    """Repair transient state, then use the canonical atomic matcher."""
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
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        cursor = await conn.execute("DELETE FROM queues WHERE user_id=?", (user_id,))
        await conn.commit()
        return bool(cursor.rowcount)


async def matchmaking_health() -> dict[str, int]:
    """Return operational counters for admin diagnostics."""
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        queue = await (await conn.execute("SELECT COUNT(*) FROM queues")).fetchone()
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
        "broken_links": int(broken[0] or 0) if broken else 0,
        "self_links": int(self_links[0] or 0) if self_links else 0,
    }

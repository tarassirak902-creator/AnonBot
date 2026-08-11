from __future__ import annotations

from datetime import datetime

import aiosqlite

from .repository import DB_PATH


def _elapsed_seconds(start_raw: str | None, now: datetime) -> int:
    if not start_raw:
        return 0
    try:
        start = datetime.fromisoformat(str(start_raw))
        current = now if start.tzinfo is None else datetime.now(start.tzinfo)
        return max(0, int((current - start).total_seconds()))
    except (TypeError, ValueError, OverflowError):
        return 0


async def is_active_chat_pair(user_id: int, partner_id: int) -> bool:
    """Return whether both reciprocal active-chat rows still describe this pair."""
    try:
        user_id = int(user_id)
        partner_id = int(partner_id)
    except (TypeError, ValueError):
        return False
    if user_id <= 0 or partner_id <= 0 or user_id == partner_id:
        return False

    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        row = await (
            await conn.execute(
                """
                SELECT 1
                FROM active_chats a
                JOIN active_chats b
                  ON b.user_id=a.partner_id AND b.partner_id=a.user_id
                WHERE a.user_id=? AND a.partner_id=?
                """,
                (user_id, partner_id),
            )
        ).fetchone()
    return row is not None


async def expire_chat_pair_if_active(
    user_id: int,
    partner_id: int,
    *,
    min_completed_seconds: int = 60,
) -> bool:
    """Atomically account and tear down exactly one still-active reciprocal pair."""
    try:
        user_id = int(user_id)
        partner_id = int(partner_id)
        min_completed_seconds = max(0, int(min_completed_seconds))
    except (TypeError, ValueError):
        return False
    if user_id <= 0 or partner_id <= 0 or user_id == partner_id:
        return False

    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("BEGIN IMMEDIATE")
        try:
            pair = await (
                await conn.execute(
                    """
                    SELECT 1
                    FROM active_chats a
                    JOIN active_chats b
                      ON b.user_id=a.partner_id AND b.partner_id=a.user_id
                    WHERE a.user_id=? AND a.partner_id=?
                    """,
                    (user_id, partner_id),
                )
            ).fetchone()
            if not pair:
                await conn.rollback()
                return False

            starts = await (
                await conn.execute(
                    "SELECT user_id,current_chat_start FROM users WHERE user_id IN (?,?)",
                    (user_id, partner_id),
                )
            ).fetchall()
            start_by_user = {int(row[0]): row[1] for row in starts}
            now = datetime.now()
            now_iso = now.isoformat()

            for uid in (user_id, partner_id):
                duration = _elapsed_seconds(start_by_user.get(uid), now)
                await conn.execute(
                    """
                    UPDATE users
                       SET chat_time_seconds=COALESCE(chat_time_seconds,0)+?,
                           completed_dialogs=COALESCE(completed_dialogs,0)+CASE WHEN ?>=? THEN 1 ELSE 0 END,
                           current_chat_start=NULL,
                           last_activity=?
                     WHERE user_id=?
                    """,
                    (duration, duration, min_completed_seconds, now_iso, uid),
                )

            await conn.execute(
                "DELETE FROM active_chats WHERE user_id IN (?,?) OR partner_id IN (?,?)",
                (user_id, partner_id, user_id, partner_id),
            )
            await conn.execute(
                "DELETE FROM queues WHERE user_id IN (?,?)",
                (user_id, partner_id),
            )
            await conn.commit()
            return True
        except Exception:
            await conn.rollback()
            raise


async def end_chat(user_id: int):
    """Atomically remove a chat pair and clear both users' session start markers.

    Session timestamps are set before match notifications are delivered. If that
    delivery fails, the chat must be torn down without leaving stale
    ``current_chat_start`` values that could later be counted as completed chat
    time by an unrelated action.
    """
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return None
    if user_id <= 0:
        return None

    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("BEGIN IMMEDIATE")
        try:
            row = await (
                await conn.execute(
                    "SELECT partner_id FROM active_chats WHERE user_id=?",
                    (user_id,),
                )
            ).fetchone()

            if not row:
                await conn.execute("DELETE FROM queues WHERE user_id=?", (user_id,))
                await conn.execute(
                    "UPDATE users SET current_chat_start=NULL WHERE user_id=?",
                    (user_id,),
                )
                await conn.commit()
                return None

            partner_id = int(row[0])
            await conn.execute(
                "DELETE FROM active_chats WHERE user_id IN (?,?) OR partner_id IN (?,?)",
                (user_id, partner_id, user_id, partner_id),
            )
            await conn.execute(
                "DELETE FROM queues WHERE user_id IN (?,?)",
                (user_id, partner_id),
            )
            await conn.execute(
                "UPDATE users SET current_chat_start=NULL WHERE user_id IN (?,?)",
                (user_id, partner_id),
            )
            await conn.commit()
            return partner_id
        except Exception:
            await conn.rollback()
            raise

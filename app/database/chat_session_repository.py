from __future__ import annotations

import aiosqlite

from .repository import DB_PATH


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

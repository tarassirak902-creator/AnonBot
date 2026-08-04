from __future__ import annotations

import aiosqlite

from .repository import DB_PATH


async def try_match_user(user_id: int) -> int | None:
    """Atomically queue a user or create one reciprocal chat pair.

    A single IMMEDIATE transaction serializes concurrent joins. Stale queue rows
    are removed before selection, repeated joins preserve FIFO position, and a
    candidate is selected only when neither side participates in an active chat.
    """
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("BEGIN IMMEDIATE")
        try:
            requester = await (
                await conn.execute(
                    "SELECT COALESCE(blocked,0) FROM users WHERE user_id=?",
                    (user_id,),
                )
            ).fetchone()
            if not requester or bool(requester[0]):
                await conn.execute("DELETE FROM queues WHERE user_id=?", (user_id,))
                await conn.commit()
                return None

            # Remove queue rows that can never be matched. Doing this inside the
            # same transaction prevents concurrent workers from seeing stale users.
            await conn.execute(
                """DELETE FROM queues
                   WHERE user_id NOT IN (SELECT user_id FROM users)
                      OR user_id IN (
                          SELECT user_id FROM users WHERE COALESCE(blocked,0)!=0
                      )
                      OR user_id IN (
                          SELECT user_id FROM active_chats
                          UNION
                          SELECT partner_id FROM active_chats
                      )"""
            )

            current = await (
                await conn.execute(
                    """SELECT a.partner_id
                       FROM active_chats a
                       JOIN active_chats b
                         ON b.user_id=a.partner_id AND b.partner_id=a.user_id
                      WHERE a.user_id=?""",
                    (user_id,),
                )
            ).fetchone()
            if current:
                await conn.execute("DELETE FROM queues WHERE user_id=?", (user_id,))
                await conn.commit()
                return None

            # Clear only inconsistent one-sided references involving requester.
            await conn.execute(
                "DELETE FROM active_chats WHERE user_id=? OR partner_id=?",
                (user_id, user_id),
            )

            candidate = await (
                await conn.execute(
                    """SELECT q.user_id
                       FROM queues q
                       JOIN users u ON u.user_id=q.user_id
                      WHERE q.user_id!=?
                        AND COALESCE(u.blocked,0)=0
                        AND NOT EXISTS (
                            SELECT 1 FROM active_chats a
                             WHERE a.user_id=q.user_id OR a.partner_id=q.user_id
                        )
                      ORDER BY q.created_at ASC, q.rowid ASC
                      LIMIT 1""",
                    (user_id,),
                )
            ).fetchone()

            if candidate is None:
                # INSERT OR IGNORE keeps the original created_at, so repeated taps
                # do not push a waiting user to the end of the queue.
                await conn.execute(
                    "INSERT OR IGNORE INTO queues(user_id,created_at) "
                    "VALUES (?,CURRENT_TIMESTAMP)",
                    (user_id,),
                )
                await conn.commit()
                return None

            partner_id = int(candidate[0])
            await conn.execute(
                "DELETE FROM queues WHERE user_id IN (?,?)",
                (user_id, partner_id),
            )
            await conn.executemany(
                "INSERT INTO active_chats(user_id,partner_id,created_at) "
                "VALUES (?,?,CURRENT_TIMESTAMP)",
                [(user_id, partner_id), (partner_id, user_id)],
            )
            await conn.commit()
            return partner_id
        except Exception:
            await conn.rollback()
            raise

from __future__ import annotations

import aiosqlite

from .repository import DB_PATH


async def try_match_user(user_id: int) -> int | None:
    """Atomically queue a user or create one reciprocal chat pair.

    The transaction excludes blocked/missing users, removes inconsistent rows for
    the requester, and never selects a candidate referenced by any active chat.
    This prevents one user from being matched into two conversations even when a
    previous process left a one-sided row behind.
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

            # Do not disturb a valid existing dialog. Remove only an inconsistent
            # one-sided row for the requester before attempting a new match.
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

            await conn.execute(
                "DELETE FROM active_chats WHERE user_id=? OR partner_id=?",
                (user_id, user_id),
            )
            await conn.execute("DELETE FROM queues WHERE user_id=?", (user_id,))

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
                await conn.execute(
                    "INSERT INTO queues(user_id,created_at) VALUES (?,CURRENT_TIMESTAMP) "
                    "ON CONFLICT(user_id) DO UPDATE SET created_at=CURRENT_TIMESTAMP",
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

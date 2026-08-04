from __future__ import annotations

import aiosqlite

from .repository import DB_PATH


async def claim_waiting_duel(duel_id: int, partner_id: int, amount: int):
    """Atomically transition one duel from waiting to active."""
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("BEGIN IMMEDIATE")
        cursor = await conn.execute(
            """
            UPDATE game_duels
               SET status='active'
             WHERE id=? AND partner_id=? AND amount=? AND status='waiting'
            RETURNING id,creator_id,partner_id,amount,status,game_type
            """,
            (duel_id, partner_id, amount),
        )
        row = await cursor.fetchone()
        if row is None:
            await conn.rollback()
            return None
        await conn.commit()
        return row


async def settle_active_duel(duel_id: int, winner_id: int | None) -> int | None:
    """Atomically credit the result and mark an active duel completed.

    ``winner_id=None`` means a draw and returns the original stake. Otherwise
    the winner receives 90% of the combined pot. Returns the credited amount.
    """
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("BEGIN IMMEDIATE")
        row = await (
            await conn.execute(
                "SELECT creator_id,partner_id,amount FROM game_duels "
                "WHERE id=? AND status='active'",
                (duel_id,),
            )
        ).fetchone()
        if row is None:
            await conn.rollback()
            return None

        creator_id, partner_id, amount = map(int, row)
        if winner_id is None:
            await conn.executemany(
                "UPDATE users SET stars_balance=stars_balance+? WHERE user_id=?",
                [(amount, creator_id), (amount, partner_id)],
            )
            credited = amount
        else:
            if int(winner_id) not in {creator_id, partner_id}:
                await conn.rollback()
                return None
            credited = int(amount * 2 * 0.90)
            await conn.execute(
                "UPDATE users SET stars_balance=stars_balance+? WHERE user_id=?",
                (credited, int(winner_id)),
            )

        cursor = await conn.execute(
            "UPDATE game_duels SET status='completed' WHERE id=? AND status='active'",
            (duel_id,),
        )
        if cursor.rowcount != 1:
            await conn.rollback()
            return None
        await conn.commit()
        return credited


async def refund_failed_duel(duel_id: int) -> bool:
    """Refund both stakes to internal balances after a game execution failure."""
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("BEGIN IMMEDIATE")
        row = await (
            await conn.execute(
                "SELECT creator_id,partner_id,amount FROM game_duels "
                "WHERE id=? AND status='active'",
                (duel_id,),
            )
        ).fetchone()
        if row is None:
            await conn.rollback()
            return False
        creator_id, partner_id, amount = map(int, row)
        await conn.executemany(
            "UPDATE users SET stars_balance=stars_balance+? WHERE user_id=?",
            [(amount, creator_id), (amount, partner_id)],
        )
        cursor = await conn.execute(
            "UPDATE game_duels SET status='failed' WHERE id=? AND status='active'",
            (duel_id,),
        )
        if cursor.rowcount != 1:
            await conn.rollback()
            return False
        await conn.commit()
        return True

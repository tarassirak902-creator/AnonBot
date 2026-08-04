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


async def complete_active_duel(duel_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        cursor = await conn.execute(
            "UPDATE game_duels SET status='completed' WHERE id=? AND status='active'",
            (duel_id,),
        )
        await conn.commit()
        return cursor.rowcount == 1


async def fail_active_duel(duel_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        cursor = await conn.execute(
            "UPDATE game_duels SET status='failed' WHERE id=? AND status='active'",
            (duel_id,),
        )
        await conn.commit()
        return cursor.rowcount == 1

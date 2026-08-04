from __future__ import annotations

import aiosqlite

from .repository import DB_PATH


async def _ensure_duel_schema(conn: aiosqlite.Connection) -> None:
    columns = await (await conn.execute("PRAGMA table_info(game_duels)")).fetchall()
    names = {str(row[1]) for row in columns}
    if "telegram_payment_charge_id" not in names:
        await conn.execute(
            "ALTER TABLE game_duels ADD COLUMN telegram_payment_charge_id TEXT"
        )
    if "created_at" not in names:
        await conn.execute("ALTER TABLE game_duels ADD COLUMN created_at TEXT")
        await conn.execute(
            "UPDATE game_duels SET created_at=COALESCE(created_at,CURRENT_TIMESTAMP)"
        )
    await conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_game_duels_charge "
        "ON game_duels(telegram_payment_charge_id) "
        "WHERE telegram_payment_charge_id IS NOT NULL"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_game_duels_pair_status "
        "ON game_duels(creator_id,partner_id,status)"
    )


async def create_waiting_duel_from_payment(
    *,
    charge_id: str,
    creator_id: int,
    partner_id: int,
    amount: int,
    game_type: str,
) -> int | None:
    """Create the first paid duel stake exactly once.

    The active anonymous chat, duplicate Telegram charge and any existing waiting
    or active duel for the same unordered pair are checked in one write lock.
    Returns the new duel ID, or ``None`` when the charge/order is no longer valid.
    """
    if not charge_id or creator_id == partner_id or amount < 1 or not game_type:
        raise ValueError("invalid duel creation")

    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("BEGIN IMMEDIATE")
        await _ensure_duel_schema(conn)

        duplicate = await (
            await conn.execute(
                "SELECT id FROM game_duels WHERE telegram_payment_charge_id=?",
                (charge_id,),
            )
        ).fetchone()
        if duplicate:
            await conn.rollback()
            return None

        reciprocal = await (
            await conn.execute(
                """SELECT 1
                     FROM active_chats a
                     JOIN active_chats b
                       ON b.user_id=a.partner_id AND b.partner_id=a.user_id
                    WHERE a.user_id=? AND a.partner_id=?""",
                (creator_id, partner_id),
            )
        ).fetchone()
        if not reciprocal:
            await conn.rollback()
            return None

        existing = await (
            await conn.execute(
                """SELECT id FROM game_duels
                    WHERE status IN ('waiting','active')
                      AND ((creator_id=? AND partner_id=?)
                        OR (creator_id=? AND partner_id=?))
                    LIMIT 1""",
                (creator_id, partner_id, partner_id, creator_id),
            )
        ).fetchone()
        if existing:
            await conn.rollback()
            return None

        cursor = await conn.execute(
            """INSERT INTO game_duels
               (creator_id,partner_id,amount,status,game_type,
                telegram_payment_charge_id,created_at)
               VALUES (?,?,?,'waiting',?,?,CURRENT_TIMESTAMP)""",
            (creator_id, partner_id, amount, game_type, charge_id),
        )
        duel_id = int(cursor.lastrowid)
        await conn.commit()
        return duel_id


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
    """Atomically credit the result and mark an active duel completed."""
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

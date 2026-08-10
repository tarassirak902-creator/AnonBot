from __future__ import annotations

from datetime import datetime

import aiosqlite

from .repository import DB_PATH


async def _ensure_charge_column(conn: aiosqlite.Connection) -> None:
    columns = await (await conn.execute("PRAGMA table_info(purchases)")).fetchall()
    if "telegram_payment_charge_id" not in {str(row[1]) for row in columns}:
        await conn.execute("ALTER TABLE purchases ADD COLUMN telegram_payment_charge_id TEXT")
    await conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_purchases_charge_id "
        "ON purchases(telegram_payment_charge_id) "
        "WHERE telegram_payment_charge_id IS NOT NULL"
    )


async def apply_chat_reveal_payment(
    *,
    charge_id: str,
    buyer_id: int,
    partner_id: int,
    amount: int,
) -> bool:
    """Atomically persist a reveal purchase for the buyer's latest matched partner."""
    try:
        buyer_id = int(buyer_id)
        partner_id = int(partner_id)
        amount = int(amount)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid reveal payment") from exc
    if not charge_id or buyer_id <= 0 or partner_id <= 0 or buyer_id == partner_id or amount <= 0:
        raise ValueError("invalid reveal payment")

    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("BEGIN IMMEDIATE")
        try:
            await _ensure_charge_column(conn)
            duplicate = await (
                await conn.execute(
                    "SELECT 1 FROM purchases WHERE telegram_payment_charge_id=?",
                    (charge_id,),
                )
            ).fetchone()
            if duplicate:
                await conn.rollback()
                return False

            latest = await (
                await conn.execute(
                    "SELECT partner_id FROM recent_partners WHERE user_id=? "
                    "ORDER BY datetime(last_chat_at) DESC, rowid DESC LIMIT 1",
                    (buyer_id,),
                )
            ).fetchone()
            if not latest or int(latest[0]) != partner_id:
                raise ValueError("reveal target is not the latest matched partner")

            setting = await (
                await conn.execute("SELECT value FROM settings WHERE key='reveal_cost'")
            ).fetchone()
            if not setting or int(setting[0]) != amount:
                raise ValueError("reveal cost changed")

            users = await (
                await conn.execute(
                    "SELECT COUNT(*) FROM users WHERE user_id IN (?,?)",
                    (buyer_id, partner_id),
                )
            ).fetchone()
            if not users or int(users[0]) != 2:
                raise ValueError("reveal users are unavailable")

            await conn.execute(
                "UPDATE users SET total_stars_spent=COALESCE(total_stars_spent,0)+? WHERE user_id=?",
                (amount, buyer_id),
            )
            await conn.execute(
                "INSERT INTO purchases "
                "(buyer_id,receiver_id,gift_id,price_stars,type,timestamp,telegram_payment_charge_id) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    buyer_id,
                    partner_id,
                    0,
                    amount,
                    "reveal",
                    datetime.now().isoformat(),
                    charge_id,
                ),
            )
        except Exception:
            await conn.rollback()
            raise
        await conn.commit()
        return True

from __future__ import annotations

from datetime import datetime, timedelta

import aiosqlite

from .repository import DB_PATH


async def _ensure_payment_schema(conn: aiosqlite.Connection) -> None:
    await conn.execute(
        "ALTER TABLE purchases ADD COLUMN telegram_payment_charge_id TEXT"
    )


async def _ensure_payment_schema_safe(conn: aiosqlite.Connection) -> None:
    columns = await (await conn.execute("PRAGMA table_info(purchases)")).fetchall()
    if "telegram_payment_charge_id" not in {row[1] for row in columns}:
        await _ensure_payment_schema(conn)
    await conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_purchases_charge_id "
        "ON purchases(telegram_payment_charge_id) "
        "WHERE telegram_payment_charge_id IS NOT NULL"
    )


async def apply_question_stars_payment(
    *,
    charge_id: str,
    buyer_id: int,
    receiver_id: int,
    amount: int,
) -> bool:
    """Atomically credit question Stars and persist purchase/statistics.

    Returns ``False`` when the Telegram charge was already applied. All database
    side effects happen in one ``BEGIN IMMEDIATE`` transaction.
    """
    if not charge_id or buyer_id == receiver_id or amount < 1:
        raise ValueError("invalid question Stars payment")

    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("BEGIN IMMEDIATE")
        await _ensure_payment_schema_safe(conn)

        existing = await (
            await conn.execute(
                "SELECT 1 FROM purchases WHERE telegram_payment_charge_id=?",
                (charge_id,),
            )
        ).fetchone()
        if existing:
            await conn.rollback()
            return False

        receiver = await (
            await conn.execute("SELECT 1 FROM users WHERE user_id=?", (receiver_id,))
        ).fetchone()
        buyer = await (
            await conn.execute("SELECT 1 FROM users WHERE user_id=?", (buyer_id,))
        ).fetchone()
        if not receiver or not buyer:
            await conn.rollback()
            raise ValueError("buyer or receiver does not exist")

        await conn.execute(
            "UPDATE users SET stars_balance=COALESCE(stars_balance,0)+? WHERE user_id=?",
            (amount, receiver_id),
        )
        await conn.execute(
            "UPDATE users SET total_stars_spent=COALESCE(total_stars_spent,0)+? WHERE user_id=?",
            (amount, buyer_id),
        )
        await conn.execute(
            "INSERT INTO purchases "
            "(buyer_id,receiver_id,gift_id,price_stars,type,timestamp,telegram_payment_charge_id) "
            "VALUES (?,?,?,?,?,?,?)",
            (buyer_id, receiver_id, 0, amount, "question_stars", now, charge_id),
        )
        await conn.execute(
            "INSERT INTO logs(user_id,action,details,timestamp) VALUES (?,?,?,?)",
            (
                buyer_id,
                "question_stars_sent",
                f"receiver_id={receiver_id}; stars={amount}; charge_id={charge_id}",
                now,
            ),
        )
        await conn.commit()
        return True


async def apply_vip_payment(
    *,
    charge_id: str,
    buyer_id: int,
    receiver_id: int,
    amount: int,
    days: int,
    purchase_type: str,
) -> bool:
    """Atomically extend VIP, record spending and persist the purchase."""
    if not charge_id or amount < 1 or days < 1:
        raise ValueError("invalid VIP payment")

    now = datetime.now()
    now_iso = now.isoformat()
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("BEGIN IMMEDIATE")
        await _ensure_payment_schema_safe(conn)

        existing = await (
            await conn.execute(
                "SELECT 1 FROM purchases WHERE telegram_payment_charge_id=?",
                (charge_id,),
            )
        ).fetchone()
        if existing:
            await conn.rollback()
            return False

        receiver = await (
            await conn.execute(
                "SELECT vip_expires_at FROM users WHERE user_id=?", (receiver_id,)
            )
        ).fetchone()
        buyer = await (
            await conn.execute("SELECT 1 FROM users WHERE user_id=?", (buyer_id,))
        ).fetchone()
        if not receiver or not buyer:
            await conn.rollback()
            raise ValueError("buyer or receiver does not exist")

        base = now
        if receiver[0]:
            try:
                current = datetime.fromisoformat(receiver[0])
                if current > now:
                    base = current
            except (TypeError, ValueError):
                pass
        expires = (base + timedelta(days=days)).isoformat()

        await conn.execute(
            "UPDATE users SET is_vip=1,vip_expires_at=? WHERE user_id=?",
            (expires, receiver_id),
        )
        await conn.execute(
            "UPDATE users SET total_stars_spent=COALESCE(total_stars_spent,0)+? WHERE user_id=?",
            (amount, buyer_id),
        )
        await conn.execute(
            "INSERT INTO purchases "
            "(buyer_id,receiver_id,gift_id,price_stars,type,timestamp,telegram_payment_charge_id) "
            "VALUES (?,?,?,?,?,?,?)",
            (buyer_id, receiver_id, 0, amount, purchase_type, now_iso, charge_id),
        )
        await conn.execute(
            "INSERT INTO logs(user_id,action,details,timestamp) VALUES (?,?,?,?)",
            (
                buyer_id,
                "question_vip_sent" if purchase_type == "question_vip" else "vip_activated",
                f"receiver_id={receiver_id}; days={days}; stars={amount}; charge_id={charge_id}",
                now_iso,
            ),
        )
        await conn.commit()
        return True

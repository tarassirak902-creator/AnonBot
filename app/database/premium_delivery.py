from __future__ import annotations

from datetime import datetime

import aiosqlite

from .repository import DB_PATH


_ALLOWED_STATUSES = {"pending", "delivering", "delivered", "failed"}


async def _ensure_schema(conn: aiosqlite.Connection) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS premium_deliveries (
            charge_id TEXT PRIMARY KEY,
            buyer_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            months INTEGER NOT NULL,
            stars INTEGER NOT NULL,
            payload TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('pending','delivering','delivered','failed')),
            created_at TEXT NOT NULL,
            delivery_started_at TEXT,
            delivered_at TEXT,
            failed_at TEXT,
            error TEXT
        )
        """
    )


async def register_premium_delivery(
    *,
    charge_id: str,
    buyer_id: int,
    receiver_id: int,
    months: int,
    stars: int,
    payload: str,
) -> str:
    """Persist a paid Premium order before calling Telegram.

    Returns the existing/new status. Conflicting metadata for the same charge is
    rejected because a Telegram charge must identify exactly one order.
    """
    if not charge_id or buyer_id == receiver_id or months not in {3, 6, 12} or stars < 1:
        raise ValueError("invalid Premium delivery")

    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("BEGIN IMMEDIATE")
        await _ensure_schema(conn)
        row = await (
            await conn.execute(
                "SELECT buyer_id,receiver_id,months,stars,payload,status "
                "FROM premium_deliveries WHERE charge_id=?",
                (charge_id,),
            )
        ).fetchone()
        if row:
            if row[:5] != (buyer_id, receiver_id, months, stars, payload):
                await conn.rollback()
                raise ValueError("conflicting Premium charge metadata")
            await conn.rollback()
            status = str(row[5])
            if status not in _ALLOWED_STATUSES:
                raise RuntimeError("invalid Premium delivery status")
            return status

        await conn.execute(
            "INSERT INTO premium_deliveries "
            "(charge_id,buyer_id,receiver_id,months,stars,payload,status,created_at) "
            "VALUES (?,?,?,?,?,?, 'pending', ?)",
            (charge_id, buyer_id, receiver_id, months, stars, payload, now),
        )
        await conn.commit()
        return "pending"


async def claim_premium_delivery(charge_id: str) -> bool:
    """Move a pending order to delivering exactly once.

    A delivery left in ``delivering`` is intentionally not retried automatically:
    Telegram may already have granted Premium before the process crashed.
    """
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("BEGIN IMMEDIATE")
        await _ensure_schema(conn)
        cursor = await conn.execute(
            "UPDATE premium_deliveries SET status='delivering',delivery_started_at=?,error=NULL "
            "WHERE charge_id=? AND status='pending'",
            (now, charge_id),
        )
        await conn.commit()
        return cursor.rowcount == 1


async def mark_premium_delivery_failed(charge_id: str, error: str) -> None:
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await _ensure_schema(conn)
        await conn.execute(
            "UPDATE premium_deliveries SET status='failed',failed_at=?,error=? "
            "WHERE charge_id=? AND status='delivering'",
            (now, error[:2000], charge_id),
        )
        await conn.commit()


async def complete_premium_delivery(charge_id: str) -> bool:
    """Atomically mark delivery and persist purchase/statistics after Telegram succeeds."""
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("BEGIN IMMEDIATE")
        await _ensure_schema(conn)
        columns = await (await conn.execute("PRAGMA table_info(purchases)")).fetchall()
        if "telegram_payment_charge_id" not in {row[1] for row in columns}:
            await conn.execute("ALTER TABLE purchases ADD COLUMN telegram_payment_charge_id TEXT")
        await conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_purchases_charge_id "
            "ON purchases(telegram_payment_charge_id) "
            "WHERE telegram_payment_charge_id IS NOT NULL"
        )

        row = await (
            await conn.execute(
                "SELECT buyer_id,receiver_id,months,stars,status "
                "FROM premium_deliveries WHERE charge_id=?",
                (charge_id,),
            )
        ).fetchone()
        if not row or row[4] != "delivering":
            await conn.rollback()
            return False

        buyer_id, receiver_id, months, stars, _ = row
        await conn.execute(
            "UPDATE users SET total_stars_spent=COALESCE(total_stars_spent,0)+? WHERE user_id=?",
            (stars, buyer_id),
        )
        await conn.execute(
            "INSERT INTO purchases "
            "(buyer_id,receiver_id,gift_id,price_stars,type,timestamp,telegram_payment_charge_id) "
            "VALUES (?,?,?,?,?,?,?)",
            (buyer_id, receiver_id, 0, stars, "question_premium", now, charge_id),
        )
        await conn.execute(
            "INSERT INTO logs(user_id,action,details,timestamp) VALUES (?,?,?,?)",
            (
                buyer_id,
                "question_premium_sent",
                f"receiver_id={receiver_id}; months={months}; stars={stars}; charge_id={charge_id}",
                now,
            ),
        )
        await conn.execute(
            "UPDATE premium_deliveries SET status='delivered',delivered_at=?,error=NULL "
            "WHERE charge_id=? AND status='delivering'",
            (now, charge_id),
        )
        await conn.commit()
        return True


async def get_premium_delivery(charge_id: str):
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await _ensure_schema(conn)
        return await (
            await conn.execute(
                "SELECT charge_id,buyer_id,receiver_id,months,stars,status,error "
                "FROM premium_deliveries WHERE charge_id=?",
                (charge_id,),
            )
        ).fetchone()

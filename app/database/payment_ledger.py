from __future__ import annotations

from datetime import datetime, timedelta

import aiosqlite

from .repository import DB_PATH


async def _ensure_payment_ledger(conn: aiosqlite.Connection) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS payment_ledger (
            charge_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            payload TEXT NOT NULL,
            total_amount INTEGER NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('processing','completed')),
            started_at TEXT NOT NULL,
            completed_at TEXT
        )
        """
    )


async def claim_payment_processing(
    charge_id: str,
    user_id: int,
    payload: str,
    total_amount: int,
    *,
    stale_after_seconds: int = 900,
) -> bool:
    """Atomically claims a Telegram payment for one processing attempt.

    Completed charges are never processed again. A stale ``processing`` claim may
    be recovered after the configured timeout, which protects against a process
    crash between claiming the update and applying its side effects.
    """
    if not charge_id:
        return False

    now = datetime.now()
    stale_before = (now - timedelta(seconds=max(60, stale_after_seconds))).isoformat()
    now_iso = now.isoformat()

    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("BEGIN IMMEDIATE")
        await _ensure_payment_ledger(conn)
        row = await (
            await conn.execute(
                "SELECT user_id,payload,total_amount,status,started_at "
                "FROM payment_ledger WHERE charge_id=?",
                (charge_id,),
            )
        ).fetchone()

        if row is None:
            await conn.execute(
                "INSERT INTO payment_ledger "
                "(charge_id,user_id,payload,total_amount,status,started_at) "
                "VALUES (?,?,?,?, 'processing', ?)",
                (charge_id, user_id, payload, total_amount, now_iso),
            )
            await conn.commit()
            return True

        stored_user, stored_payload, stored_amount, status, started_at = row
        if (
            int(stored_user) != int(user_id)
            or stored_payload != payload
            or int(stored_amount) != int(total_amount)
        ):
            await conn.rollback()
            return False

        if status == "completed" or (started_at and started_at > stale_before):
            await conn.rollback()
            return False

        cursor = await conn.execute(
            "UPDATE payment_ledger SET status='processing',started_at=?,completed_at=NULL "
            "WHERE charge_id=? AND status='processing' AND started_at<=?",
            (now_iso, charge_id, stale_before),
        )
        await conn.commit()
        return cursor.rowcount == 1


async def complete_payment_processing(charge_id: str) -> None:
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await _ensure_payment_ledger(conn)
        await conn.execute(
            "UPDATE payment_ledger SET status='completed',completed_at=? "
            "WHERE charge_id=? AND status='processing'",
            (datetime.now().isoformat(), charge_id),
        )
        await conn.commit()


async def release_payment_processing(charge_id: str) -> None:
    """Releases a non-completed claim after a handled exception.

    Deleting only ``processing`` rows makes an immediate Telegram retry possible,
    while already completed payments remain permanently idempotent.
    """
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await _ensure_payment_ledger(conn)
        await conn.execute(
            "DELETE FROM payment_ledger WHERE charge_id=? AND status='processing'",
            (charge_id,),
        )
        await conn.commit()

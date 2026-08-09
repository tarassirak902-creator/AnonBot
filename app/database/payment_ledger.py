from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import sqlite3

import aiosqlite

from .repository import DB_PATH


@dataclass(frozen=True)
class PaymentLedgerMetrics:
    completed_24h: int
    completed_stars_24h: int
    processing: int
    failed: int
    unresolved: int


@dataclass(frozen=True)
class PaymentLedgerIssue:
    user_id: int
    payment_type: str
    total_amount: int
    state: str
    started_at: str
    last_error: str | None


async def _ensure_optional_column(
    conn: aiosqlite.Connection,
    column_name: str,
    definition: str,
) -> None:
    columns = await (await conn.execute("PRAGMA table_info(payment_ledger)")).fetchall()
    if column_name in {str(column[1]) for column in columns}:
        return
    try:
        await conn.execute(
            f"ALTER TABLE payment_ledger ADD COLUMN {column_name} {definition}"
        )
    except sqlite3.OperationalError as exc:
        # Another process may have completed the same additive migration.
        if "duplicate column name" not in str(exc).lower():
            raise


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
    await _ensure_optional_column(conn, "failed_at", "TEXT")
    await _ensure_optional_column(conn, "last_error", "TEXT")


def _payment_type(payload: str) -> str:
    """Return a privacy-safe product family without exposing payload arguments."""
    value = (payload or "").strip()
    if not value:
        return "unknown"
    if ":" in value:
        return value.split(":", 1)[0][:48]
    if value.startswith("vip_subscription"):
        return "vip_subscription"
    if value.startswith("ad_order_"):
        return "ad_order"
    if value.startswith("duel_create_"):
        return "duel_create"
    if value.startswith("duel_accept_"):
        return "duel_accept"
    if value.startswith("solo_"):
        return "solo_game"
    if value.startswith("gift_"):
        return "gift"
    if value.startswith("reveal_"):
        return "reveal"
    return value.split("_", 1)[0][:48]


async def claim_payment_processing(
    charge_id: str,
    user_id: int,
    payload: str,
    total_amount: int,
) -> bool:
    """Atomically claims a Telegram charge exactly once.

    Existing charge IDs are never automatically reclaimed, including records left
    in ``processing`` after a crash. Reclaiming such a record is unsafe because
    business side effects may already have happened before the process stopped.
    Failed or interrupted charges therefore remain available for manual support
    reconciliation instead of risking a duplicate gift, balance credit or VIP.
    """
    if not charge_id:
        return False

    now_iso = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("BEGIN IMMEDIATE")
        await _ensure_payment_ledger(conn)

        cursor = await conn.execute(
            "INSERT OR IGNORE INTO payment_ledger "
            "(charge_id,user_id,payload,total_amount,status,started_at) "
            "VALUES (?,?,?,?, 'processing', ?)",
            (charge_id, user_id, payload, total_amount, now_iso),
        )
        if cursor.rowcount == 1:
            await conn.commit()
            return True

        row = await (
            await conn.execute(
                "SELECT user_id,payload,total_amount FROM payment_ledger WHERE charge_id=?",
                (charge_id,),
            )
        ).fetchone()
        await conn.rollback()

        # A conflicting reuse of the same Telegram charge is rejected just like a
        # duplicate. Callers log the event without exposing payment data to users.
        if row is None:
            return False
        stored_user, stored_payload, stored_amount = row
        return False if (
            int(stored_user) == int(user_id)
            and stored_payload == payload
            and int(stored_amount) == int(total_amount)
        ) else False


async def complete_payment_processing(charge_id: str) -> None:
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await _ensure_payment_ledger(conn)
        await conn.execute(
            "UPDATE payment_ledger "
            "SET status='completed',completed_at=?,failed_at=NULL,last_error=NULL "
            "WHERE charge_id=? AND status='processing'",
            (datetime.now().isoformat(), charge_id),
        )
        await conn.commit()


async def release_payment_processing(charge_id: str, error: str | None = None) -> None:
    """Records a failed/interrupted attempt without making it retryable.

    The historical function name is retained for compatibility with middleware.
    The claim is intentionally not deleted: an automatic retry could repeat side
    effects that committed before an exception was raised.
    """
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await _ensure_payment_ledger(conn)
        await conn.execute(
            "UPDATE payment_ledger SET failed_at=?,last_error=? "
            "WHERE charge_id=? AND status='processing'",
            (datetime.now().isoformat(), (error or "")[:2000], charge_id),
        )
        await conn.commit()


async def get_payment_ledger_metrics() -> PaymentLedgerMetrics:
    """Return aggregate payment health without exposing charge identifiers."""
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await _ensure_payment_ledger(conn)
        completed = await (
            await conn.execute(
                "SELECT COUNT(*),COALESCE(SUM(total_amount),0) FROM payment_ledger "
                "WHERE status='completed' AND completed_at>=datetime('now','-1 day')"
            )
        ).fetchone()
        processing_row = await (
            await conn.execute(
                "SELECT COUNT(*) FROM payment_ledger "
                "WHERE status='processing' AND failed_at IS NULL"
            )
        ).fetchone()
        failed_row = await (
            await conn.execute(
                "SELECT COUNT(*) FROM payment_ledger "
                "WHERE status='processing' AND failed_at IS NOT NULL"
            )
        ).fetchone()

    processing = int((processing_row[0] if processing_row else 0) or 0)
    failed = int((failed_row[0] if failed_row else 0) or 0)
    return PaymentLedgerMetrics(
        completed_24h=int((completed[0] if completed else 0) or 0),
        completed_stars_24h=int((completed[1] if completed else 0) or 0),
        processing=processing,
        failed=failed,
        unresolved=processing + failed,
    )


async def get_recent_payment_issues(limit: int = 8) -> list[PaymentLedgerIssue]:
    """Return recent unresolved payments with sanitized product type only."""
    limit = max(1, min(int(limit), 25))
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await _ensure_payment_ledger(conn)
        rows = await (
            await conn.execute(
                "SELECT user_id,payload,total_amount,started_at,failed_at,last_error "
                "FROM payment_ledger WHERE status='processing' "
                "ORDER BY started_at DESC LIMIT ?",
                (limit,),
            )
        ).fetchall()

    return [
        PaymentLedgerIssue(
            user_id=int(row[0]),
            payment_type=_payment_type(str(row[1])),
            total_amount=int(row[2]),
            state="failed" if row[4] else "processing",
            started_at=str(row[3]),
            last_error=(str(row[5])[:160] if row[5] else None),
        )
        for row in rows
    ]

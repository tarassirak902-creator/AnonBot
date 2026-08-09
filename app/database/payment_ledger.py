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
    ledger_id: int
    user_id: int
    payment_type: str
    total_amount: int
    state: str
    started_at: str
    last_error: str | None


@dataclass(frozen=True)
class PaymentProductMetric:
    payment_type: str
    purchases: int
    stars: int
    unique_buyers: int


@dataclass(frozen=True)
class CommercialPaymentMetrics:
    purchases: int
    stars: int
    unique_buyers: int
    average_check: int
    products: tuple[PaymentProductMetric, ...]


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
    await _ensure_optional_column(conn, "resolved_at", "TEXT")
    await _ensure_optional_column(conn, "resolved_by", "INTEGER")
    await _ensure_optional_column(conn, "resolution_note", "TEXT")


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
    """Atomically claim a Telegram charge exactly once.

    Existing charge IDs are never automatically reclaimed. A failed or manually
    reconciled record continues to block the same Telegram charge forever because
    business side effects may already have happened before a process failure.
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

        await conn.rollback()
        return False


async def complete_payment_processing(charge_id: str) -> None:
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await _ensure_payment_ledger(conn)
        await conn.execute(
            "UPDATE payment_ledger "
            "SET status='completed',completed_at=?,failed_at=NULL,last_error=NULL,"
            "resolved_at=NULL,resolved_by=NULL,resolution_note=NULL "
            "WHERE charge_id=? AND status='processing'",
            (datetime.now().isoformat(), charge_id),
        )
        await conn.commit()


async def release_payment_processing(charge_id: str, error: str | None = None) -> None:
    """Record a failed/interrupted attempt without making it retryable."""
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await _ensure_payment_ledger(conn)
        await conn.execute(
            "UPDATE payment_ledger SET failed_at=?,last_error=? "
            "WHERE charge_id=? AND status='processing'",
            (datetime.now().isoformat(), (error or "")[:2000], charge_id),
        )
        await conn.commit()


async def resolve_payment_issue(
    ledger_id: int,
    admin_id: int,
    note: str = "Проверено администратором",
) -> bool:
    """Close a reconciliation item without replaying any payment side effects."""
    if int(ledger_id) < 1 or int(admin_id) < 1:
        return False
    safe_note = (note or "Проверено администратором").strip()[:240]
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("BEGIN IMMEDIATE")
        await _ensure_payment_ledger(conn)
        cursor = await conn.execute(
            "UPDATE payment_ledger SET resolved_at=?,resolved_by=?,resolution_note=? "
            "WHERE rowid=? AND status='processing' AND resolved_at IS NULL",
            (datetime.now().isoformat(), int(admin_id), safe_note, int(ledger_id)),
        )
        if cursor.rowcount != 1:
            await conn.rollback()
            return False
        await conn.commit()
        return True


async def get_payment_ledger_metrics() -> PaymentLedgerMetrics:
    """Return aggregate payment health without exposing charge identifiers."""
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await _ensure_payment_ledger(conn)
        completed = await (
            await conn.execute(
                "SELECT COUNT(*),COALESCE(SUM(total_amount),0) FROM payment_ledger "
                "WHERE status='completed' AND datetime(completed_at)>=datetime('now','-1 day')"
            )
        ).fetchone()
        processing_row = await (
            await conn.execute(
                "SELECT COUNT(*) FROM payment_ledger "
                "WHERE status='processing' AND failed_at IS NULL AND resolved_at IS NULL"
            )
        ).fetchone()
        failed_row = await (
            await conn.execute(
                "SELECT COUNT(*) FROM payment_ledger "
                "WHERE status='processing' AND failed_at IS NOT NULL AND resolved_at IS NULL"
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


async def get_commercial_payment_metrics(
    days: int = 7,
    *,
    product_limit: int = 6,
) -> CommercialPaymentMetrics:
    """Return completed-payment commerce metrics for a bounded rolling period."""
    days = max(1, min(int(days), 90))
    product_limit = max(1, min(int(product_limit), 12))
    modifier = f"-{days} days"

    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await _ensure_payment_ledger(conn)
        rows = await (
            await conn.execute(
                "SELECT user_id,payload,total_amount FROM payment_ledger "
                "WHERE status='completed' AND datetime(completed_at)>=datetime('now',?)",
                (modifier,),
            )
        ).fetchall()

    purchases = len(rows)
    stars = sum(int(row[2] or 0) for row in rows)
    unique_buyers = len({int(row[0]) for row in rows})
    average_check = round(stars / purchases) if purchases else 0

    products: dict[str, dict[str, object]] = {}
    for user_id, payload, total_amount in rows:
        payment_type = _payment_type(str(payload))
        bucket = products.setdefault(
            payment_type,
            {"purchases": 0, "stars": 0, "buyers": set()},
        )
        bucket["purchases"] = int(bucket["purchases"]) + 1
        bucket["stars"] = int(bucket["stars"]) + int(total_amount or 0)
        buyers = bucket["buyers"]
        if isinstance(buyers, set):
            buyers.add(int(user_id))

    ranked = sorted(
        products.items(),
        key=lambda item: (int(item[1]["stars"]), int(item[1]["purchases"])),
        reverse=True,
    )[:product_limit]
    product_metrics = tuple(
        PaymentProductMetric(
            payment_type=payment_type,
            purchases=int(values["purchases"]),
            stars=int(values["stars"]),
            unique_buyers=len(values["buyers"]) if isinstance(values["buyers"], set) else 0,
        )
        for payment_type, values in ranked
    )
    return CommercialPaymentMetrics(
        purchases=purchases,
        stars=stars,
        unique_buyers=unique_buyers,
        average_check=average_check,
        products=product_metrics,
    )


async def get_recent_payment_issues(limit: int = 8) -> list[PaymentLedgerIssue]:
    """Return unresolved payments with sanitized product type and opaque row id."""
    limit = max(1, min(int(limit), 25))
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await _ensure_payment_ledger(conn)
        rows = await (
            await conn.execute(
                "SELECT rowid,user_id,payload,total_amount,started_at,failed_at,last_error "
                "FROM payment_ledger WHERE status='processing' AND resolved_at IS NULL "
                "ORDER BY started_at DESC LIMIT ?",
                (limit,),
            )
        ).fetchall()

    return [
        PaymentLedgerIssue(
            ledger_id=int(row[0]),
            user_id=int(row[1]),
            payment_type=_payment_type(str(row[2])),
            total_amount=int(row[3]),
            state="failed" if row[5] else "processing",
            started_at=str(row[4]),
            last_error=(str(row[6])[:160] if row[6] else None),
        )
        for row in rows
    ]

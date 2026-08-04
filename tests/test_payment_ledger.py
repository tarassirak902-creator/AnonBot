from __future__ import annotations

import aiosqlite
import pytest

from app.database import payment_ledger


@pytest.fixture
def ledger_db(tmp_path, monkeypatch):
    db_path = tmp_path / "payments.db"
    monkeypatch.setattr(payment_ledger, "DB_PATH", str(db_path))
    return db_path


@pytest.mark.asyncio
async def test_charge_can_be_claimed_only_once(ledger_db) -> None:
    assert await payment_ledger.claim_payment_processing("charge-1", 10, "vip", 100)
    assert not await payment_ledger.claim_payment_processing("charge-1", 10, "vip", 100)


@pytest.mark.asyncio
async def test_failed_charge_is_not_automatically_retried(ledger_db) -> None:
    assert await payment_ledger.claim_payment_processing("charge-2", 10, "gift", 50)
    await payment_ledger.release_payment_processing("charge-2", "delivery failed")

    assert not await payment_ledger.claim_payment_processing("charge-2", 10, "gift", 50)

    async with aiosqlite.connect(ledger_db) as conn:
        row = await (
            await conn.execute(
                "SELECT status,failed_at,last_error FROM payment_ledger WHERE charge_id=?",
                ("charge-2",),
            )
        ).fetchone()
    assert row is not None
    assert row[0] == "processing"
    assert row[1]
    assert row[2] == "delivery failed"


@pytest.mark.asyncio
async def test_completed_charge_is_not_reprocessed(ledger_db) -> None:
    assert await payment_ledger.claim_payment_processing("charge-3", 10, "stars", 250)
    await payment_ledger.complete_payment_processing("charge-3")

    assert not await payment_ledger.claim_payment_processing("charge-3", 10, "stars", 250)

    async with aiosqlite.connect(ledger_db) as conn:
        row = await (
            await conn.execute(
                "SELECT status,completed_at,failed_at,last_error "
                "FROM payment_ledger WHERE charge_id=?",
                ("charge-3",),
            )
        ).fetchone()
    assert row is not None
    assert row[0] == "completed"
    assert row[1]
    assert row[2] is None
    assert row[3] is None


@pytest.mark.asyncio
async def test_conflicting_charge_metadata_is_rejected(ledger_db) -> None:
    assert await payment_ledger.claim_payment_processing("charge-4", 10, "gift", 50)
    assert not await payment_ledger.claim_payment_processing("charge-4", 11, "gift", 50)
    assert not await payment_ledger.claim_payment_processing("charge-4", 10, "other", 50)
    assert not await payment_ledger.claim_payment_processing("charge-4", 10, "gift", 51)

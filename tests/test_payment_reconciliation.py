from __future__ import annotations

import aiosqlite
import pytest

from app.database import payment_ledger


@pytest.mark.asyncio
async def test_payment_metrics_and_issue_list(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "payments.db")
    monkeypatch.setattr(payment_ledger, "DB_PATH", db_path)

    assert await payment_ledger.claim_payment_processing("charge-ok", 101, "vip_subscription_100", 100)
    await payment_ledger.complete_payment_processing("charge-ok")

    assert await payment_ledger.claim_payment_processing("charge-failed", 202, "question_stars:q:abc:50", 50)
    await payment_ledger.release_payment_processing("charge-failed", "RuntimeError('delivery failed')")

    assert await payment_ledger.claim_payment_processing("charge-pending", 303, "solo_darts_20", 20)

    metrics = await payment_ledger.get_payment_ledger_metrics()
    assert metrics.completed_24h == 1
    assert metrics.completed_stars_24h == 100
    assert metrics.processing == 1
    assert metrics.failed == 1
    assert metrics.unresolved == 2

    issues = await payment_ledger.get_recent_payment_issues(10)
    assert {item.user_id for item in issues} == {202, 303}
    by_user = {item.user_id: item for item in issues}
    assert by_user[202].payment_type == "question_stars"
    assert by_user[202].state == "failed"
    assert "delivery failed" in (by_user[202].last_error or "")
    assert by_user[303].payment_type == "solo_game"
    assert by_user[303].state == "processing"


@pytest.mark.asyncio
async def test_duplicate_charge_stays_single_ledger_record(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "duplicate.db")
    monkeypatch.setattr(payment_ledger, "DB_PATH", db_path)

    assert await payment_ledger.claim_payment_processing("same-charge", 404, "ad_order_9", 250)
    assert not await payment_ledger.claim_payment_processing("same-charge", 404, "ad_order_9", 250)

    async with aiosqlite.connect(db_path) as conn:
        rows = await (await conn.execute("SELECT COUNT(*) FROM payment_ledger")).fetchone()
    assert rows[0] == 1


def test_payment_type_never_exposes_payload_arguments() -> None:
    assert payment_ledger._payment_type("question_stars:q:private-ref:500") == "question_stars"
    assert payment_ledger._payment_type("ad_order_12345") == "ad_order"
    assert payment_ledger._payment_type("duel_create_22_50_darts") == "duel_create"
    assert payment_ledger._payment_type("solo_darts_25") == "solo_game"

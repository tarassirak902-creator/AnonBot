from __future__ import annotations

from datetime import datetime, timedelta

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
    assert all(item.ledger_id > 0 for item in issues)
    by_user = {item.user_id: item for item in issues}
    assert by_user[202].payment_type == "question_stars"
    assert by_user[202].state == "failed"
    assert "delivery failed" in (by_user[202].last_error or "")
    assert by_user[303].payment_type == "solo_game"
    assert by_user[303].state == "processing"


@pytest.mark.asyncio
async def test_commercial_metrics_use_completed_payments_only(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "commerce.db")
    monkeypatch.setattr(payment_ledger, "DB_PATH", db_path)

    completed = [
        ("vip-1", 101, "vip_subscription_100", 100),
        ("vip-2", 101, "vip_subscription_250", 250),
        ("gift-1", 202, "gift_user_50", 50),
    ]
    for charge_id, user_id, payload, amount in completed:
        assert await payment_ledger.claim_payment_processing(charge_id, user_id, payload, amount)
        await payment_ledger.complete_payment_processing(charge_id)

    assert await payment_ledger.claim_payment_processing("failed", 303, "ad_order_5", 900)
    await payment_ledger.release_payment_processing("failed", "not delivered")
    assert await payment_ledger.claim_payment_processing("pending", 404, "solo_darts_40", 40)

    metrics = await payment_ledger.get_commercial_payment_metrics(7)
    assert metrics.purchases == 3
    assert metrics.stars == 400
    assert metrics.unique_buyers == 2
    assert metrics.average_check == 133
    assert [item.payment_type for item in metrics.products] == ["vip_subscription", "gift"]
    assert metrics.products[0].purchases == 2
    assert metrics.products[0].stars == 350
    assert metrics.products[0].unique_buyers == 1


@pytest.mark.asyncio
async def test_commercial_period_excludes_old_completed_payments(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "period.db")
    monkeypatch.setattr(payment_ledger, "DB_PATH", db_path)

    assert await payment_ledger.claim_payment_processing("recent", 101, "gift_user_20", 20)
    await payment_ledger.complete_payment_processing("recent")
    assert await payment_ledger.claim_payment_processing("old", 202, "vip_subscription_500", 500)
    await payment_ledger.complete_payment_processing("old")

    old_time = (datetime.now() - timedelta(days=10)).isoformat()
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "UPDATE payment_ledger SET completed_at=? WHERE charge_id='old'",
            (old_time,),
        )
        await conn.commit()

    one_day = await payment_ledger.get_commercial_payment_metrics(1)
    seven_days = await payment_ledger.get_commercial_payment_metrics(7)
    thirty_days = await payment_ledger.get_commercial_payment_metrics(30)
    assert one_day.purchases == 1
    assert seven_days.purchases == 1
    assert thirty_days.purchases == 2
    assert thirty_days.stars == 520


@pytest.mark.asyncio
async def test_resolved_issue_leaves_queue_but_charge_stays_blocked(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "resolved.db")
    monkeypatch.setattr(payment_ledger, "DB_PATH", db_path)

    assert await payment_ledger.claim_payment_processing("charge-review", 505, "ad_order_17", 300)
    await payment_ledger.release_payment_processing("charge-review", "delivery uncertain")
    issues = await payment_ledger.get_recent_payment_issues(10)
    assert len(issues) == 1

    ledger_id = issues[0].ledger_id
    assert await payment_ledger.resolve_payment_issue(ledger_id, 999, "Проверено вручную")
    assert not await payment_ledger.resolve_payment_issue(ledger_id, 999)

    metrics = await payment_ledger.get_payment_ledger_metrics()
    assert metrics.unresolved == 0
    assert await payment_ledger.get_recent_payment_issues(10) == []

    # Manual reconciliation never reopens the charge for automatic execution.
    assert not await payment_ledger.claim_payment_processing("charge-review", 505, "ad_order_17", 300)

    async with aiosqlite.connect(db_path) as conn:
        row = await (
            await conn.execute(
                "SELECT status,resolved_by,resolution_note,resolved_at FROM payment_ledger WHERE charge_id=?",
                ("charge-review",),
            )
        ).fetchone()
    assert row[0] == "processing"
    assert row[1] == 999
    assert row[2] == "Проверено вручную"
    assert row[3]


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

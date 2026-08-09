from __future__ import annotations

from types import SimpleNamespace

import aiosqlite
import pytest

from app.core.action_flow import run_state_action
from app.database import payment_ledger


class FailingAnswerCallback:
    def __init__(self) -> None:
        self.data = "test_action"
        self.from_user = SimpleNamespace(id=101)

    async def answer(self, text: str, *, show_alert: bool = False) -> None:
        raise RuntimeError("callback query is too old")


@pytest.mark.asyncio
async def test_state_action_renders_even_when_callback_answer_fails() -> None:
    callback = FailingAnswerCallback()
    rendered = 0

    async def action() -> bool:
        return True

    async def render() -> None:
        nonlocal rendered
        rendered += 1

    result = await run_state_action(
        callback,
        action=action,
        render=render,
        success_text="done",
        noop_text="noop",
        error_text="failed",
    )

    assert result is True
    assert rendered == 1


@pytest.mark.asyncio
async def test_active_processing_payment_cannot_be_manually_resolved(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "active-processing.db")
    monkeypatch.setattr(payment_ledger, "DB_PATH", db_path)

    assert await payment_ledger.claim_payment_processing(
        "active-charge", 101, "gift_user_20", 20
    )
    issues = await payment_ledger.get_recent_payment_issues(10)
    assert len(issues) == 1
    assert issues[0].state == "processing"

    assert not await payment_ledger.resolve_payment_issue(issues[0].ledger_id, 999)

    async with aiosqlite.connect(db_path) as conn:
        row = await (
            await conn.execute(
                "SELECT resolved_at,failed_at FROM payment_ledger WHERE charge_id=?",
                ("active-charge",),
            )
        ).fetchone()
    assert row == (None, None)


@pytest.mark.asyncio
async def test_failed_payment_can_be_resolved_and_stays_blocked(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "failed-resolve.db")
    monkeypatch.setattr(payment_ledger, "DB_PATH", db_path)

    assert await payment_ledger.claim_payment_processing(
        "failed-charge", 202, "vip_subscription_100", 100
    )
    await payment_ledger.release_payment_processing("failed-charge", "delivery failed")

    issues = await payment_ledger.get_recent_payment_issues(10)
    assert len(issues) == 1
    assert issues[0].state == "failed"
    assert await payment_ledger.resolve_payment_issue(issues[0].ledger_id, 999)

    assert not await payment_ledger.claim_payment_processing(
        "failed-charge", 202, "vip_subscription_100", 100
    )
    assert await payment_ledger.get_recent_payment_issues(10) == []


@pytest.mark.asyncio
async def test_release_clears_stale_resolution_marker(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "stale-resolution.db")
    monkeypatch.setattr(payment_ledger, "DB_PATH", db_path)

    assert await payment_ledger.claim_payment_processing(
        "race-charge", 303, "solo_darts_20", 20
    )
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "UPDATE payment_ledger SET resolved_at='2026-01-01T00:00:00+00:00',resolved_by=1 "
            "WHERE charge_id=?",
            ("race-charge",),
        )
        await conn.commit()

    await payment_ledger.release_payment_processing("race-charge", "late failure")

    async with aiosqlite.connect(db_path) as conn:
        row = await (
            await conn.execute(
                "SELECT failed_at,resolved_at,resolved_by,resolution_note "
                "FROM payment_ledger WHERE charge_id=?",
                ("race-charge",),
            )
        ).fetchone()
    assert row[0] is not None
    assert row[1:] == (None, None, None)

    issues = await payment_ledger.get_recent_payment_issues(10)
    assert len(issues) == 1
    assert issues[0].state == "failed"


@pytest.mark.asyncio
async def test_payment_timestamps_are_recorded_in_utc(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "utc.db")
    monkeypatch.setattr(payment_ledger, "DB_PATH", db_path)

    assert await payment_ledger.claim_payment_processing(
        "utc-charge", 404, "gift_user_50", 50
    )
    await payment_ledger.complete_payment_processing("utc-charge")

    async with aiosqlite.connect(db_path) as conn:
        row = await (
            await conn.execute(
                "SELECT started_at,completed_at FROM payment_ledger WHERE charge_id=?",
                ("utc-charge",),
            )
        ).fetchone()

    assert row[0].endswith("+00:00")
    assert row[1].endswith("+00:00")

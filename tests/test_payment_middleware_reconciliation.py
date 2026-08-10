from __future__ import annotations

from datetime import datetime, timezone

import pytest
from aiogram.types import Chat, Message, SuccessfulPayment, User

from app.core import payment_middleware


def _payment_message(charge_id: str = "charge-1") -> Message:
    return Message(
        message_id=1,
        date=datetime.now(timezone.utc),
        chat=Chat(id=100, type="private"),
        from_user=User(id=100, is_bot=False, first_name="Test"),
        successful_payment=SuccessfulPayment(
            currency="XTR",
            total_amount=100,
            invoice_payload="vip_subscription_100",
            telegram_payment_charge_id=charge_id,
            provider_payment_charge_id="provider-1",
        ),
    )


@pytest.mark.asyncio
async def test_reconciliation_result_does_not_mark_charge_completed(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    async def claim(*args, **kwargs):
        return True

    async def release(charge_id: str, error: str | None = None):
        calls.append(("release", f"{charge_id}:{error}"))

    async def complete(charge_id: str):
        calls.append(("complete", charge_id))

    monkeypatch.setattr(payment_middleware.db, "claim_payment_processing", claim)
    monkeypatch.setattr(payment_middleware.db, "release_payment_processing", release)
    monkeypatch.setattr(payment_middleware.db, "complete_payment_processing", complete)

    async def handler(event, data):
        return payment_middleware.payment_reconciliation_required("business action failed")

    middleware = payment_middleware.PaymentIdempotencyMiddleware()
    result = await middleware(handler, _payment_message(), {})

    assert result is None
    assert calls == [("release", "charge-1:business action failed")]


@pytest.mark.asyncio
async def test_successful_handler_marks_charge_completed(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    async def claim(*args, **kwargs):
        return True

    async def release(charge_id: str, error: str | None = None):
        calls.append(("release", charge_id))

    async def complete(charge_id: str):
        calls.append(("complete", charge_id))

    monkeypatch.setattr(payment_middleware.db, "claim_payment_processing", claim)
    monkeypatch.setattr(payment_middleware.db, "release_payment_processing", release)
    monkeypatch.setattr(payment_middleware.db, "complete_payment_processing", complete)

    async def handler(event, data):
        return None

    middleware = payment_middleware.PaymentIdempotencyMiddleware()
    result = await middleware(handler, _payment_message("charge-ok"), {})

    assert result is None
    assert calls == [("complete", "charge-ok")]

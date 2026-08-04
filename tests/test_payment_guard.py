from __future__ import annotations

import pytest

from app.handlers import payment_guard


@pytest.mark.asyncio
async def test_rejects_unknown_payload() -> None:
    error = await payment_guard._validate_payload(1, "unknown", 100)
    assert error is not None


@pytest.mark.asyncio
async def test_validates_vip_amount() -> None:
    assert await payment_guard._validate_payload(1, "vip_subscription_100", 100) is None
    assert await payment_guard._validate_payload(1, "vip_subscription_100", 1) is not None


@pytest.mark.asyncio
async def test_rejects_invalid_stars_range() -> None:
    assert await payment_guard._validate_payload(1, "vip_subscription_100", 0) is not None
    assert await payment_guard._validate_payload(1, "vip_subscription_100", 10_001) is not None

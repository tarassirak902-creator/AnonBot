from __future__ import annotations

import aiosqlite
import pytest

from app.database import premium_delivery


async def _create_schema(path: str) -> None:
    async with aiosqlite.connect(path) as conn:
        await conn.executescript(
            """
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                total_stars_spent INTEGER DEFAULT 0
            );
            CREATE TABLE purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                buyer_id INTEGER,
                receiver_id INTEGER,
                gift_id INTEGER,
                price_stars INTEGER,
                type TEXT,
                timestamp TEXT
            );
            CREATE TABLE logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                details TEXT,
                timestamp TEXT
            );
            INSERT INTO users(user_id) VALUES (1), (2);
            """
        )
        await conn.commit()


@pytest.mark.asyncio
async def test_premium_delivery_can_be_claimed_only_once(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "premium.db")
    await _create_schema(db_path)
    monkeypatch.setattr(premium_delivery, "DB_PATH", db_path)

    status = await premium_delivery.register_premium_delivery(
        charge_id="premium-1",
        buyer_id=1,
        receiver_id=2,
        months=3,
        stars=1000,
        payload="question_premium:t:2:3:1000",
    )
    assert status == "pending"
    assert await premium_delivery.claim_premium_delivery("premium-1")
    assert not await premium_delivery.claim_premium_delivery("premium-1")

    row = await premium_delivery.get_premium_delivery("premium-1")
    assert row[5] == "delivering"


@pytest.mark.asyncio
async def test_failed_delivery_is_not_automatically_retried(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "premium.db")
    await _create_schema(db_path)
    monkeypatch.setattr(premium_delivery, "DB_PATH", db_path)

    await premium_delivery.register_premium_delivery(
        charge_id="premium-failed",
        buyer_id=1,
        receiver_id=2,
        months=6,
        stars=1500,
        payload="question_premium:t:2:6:1500",
    )
    assert await premium_delivery.claim_premium_delivery("premium-failed")
    await premium_delivery.mark_premium_delivery_failed("premium-failed", "telegram error")

    status = await premium_delivery.register_premium_delivery(
        charge_id="premium-failed",
        buyer_id=1,
        receiver_id=2,
        months=6,
        stars=1500,
        payload="question_premium:t:2:6:1500",
    )
    assert status == "failed"
    assert not await premium_delivery.claim_premium_delivery("premium-failed")


@pytest.mark.asyncio
async def test_successful_delivery_finalizes_purchase_atomically(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "premium.db")
    await _create_schema(db_path)
    monkeypatch.setattr(premium_delivery, "DB_PATH", db_path)

    await premium_delivery.register_premium_delivery(
        charge_id="premium-ok",
        buyer_id=1,
        receiver_id=2,
        months=12,
        stars=2500,
        payload="question_premium:t:2:12:2500",
    )
    assert await premium_delivery.claim_premium_delivery("premium-ok")
    assert await premium_delivery.complete_premium_delivery("premium-ok")
    assert not await premium_delivery.complete_premium_delivery("premium-ok")

    async with aiosqlite.connect(db_path) as conn:
        spent = await (await conn.execute(
            "SELECT total_stars_spent FROM users WHERE user_id=1"
        )).fetchone()
        purchase = await (await conn.execute(
            "SELECT type,price_stars FROM purchases "
            "WHERE telegram_payment_charge_id='premium-ok'"
        )).fetchone()
        status = await (await conn.execute(
            "SELECT status FROM premium_deliveries WHERE charge_id='premium-ok'"
        )).fetchone()

    assert spent[0] == 2500
    assert purchase == ("question_premium", 2500)
    assert status[0] == "delivered"


@pytest.mark.asyncio
async def test_conflicting_charge_metadata_is_rejected(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "premium.db")
    await _create_schema(db_path)
    monkeypatch.setattr(premium_delivery, "DB_PATH", db_path)

    await premium_delivery.register_premium_delivery(
        charge_id="premium-conflict",
        buyer_id=1,
        receiver_id=2,
        months=3,
        stars=1000,
        payload="question_premium:t:2:3:1000",
    )
    with pytest.raises(ValueError):
        await premium_delivery.register_premium_delivery(
            charge_id="premium-conflict",
            buyer_id=1,
            receiver_id=2,
            months=12,
            stars=2500,
            payload="question_premium:t:2:12:2500",
        )

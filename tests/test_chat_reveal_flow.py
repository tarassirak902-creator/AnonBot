from __future__ import annotations

from unittest.mock import AsyncMock

import aiosqlite
import pytest

from app.database import chat_reveal_repository, social_repository
from app.handlers import payment_guard


async def _create_reveal_db(path: str) -> None:
    async with aiosqlite.connect(path) as conn:
        await conn.executescript(
            """
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                total_stars_spent INTEGER DEFAULT 0
            );
            CREATE TABLE recent_partners (
                user_id INTEGER NOT NULL,
                partner_id INTEGER NOT NULL,
                last_chat_at TEXT NOT NULL,
                PRIMARY KEY(user_id, partner_id)
            );
            CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                buyer_id INTEGER,
                receiver_id INTEGER,
                gift_id INTEGER,
                price_stars INTEGER,
                type TEXT,
                timestamp TEXT
            );
            INSERT INTO users(user_id,total_stars_spent) VALUES (1,0),(2,0),(3,0);
            INSERT INTO settings(key,value) VALUES ('reveal_cost','100');
            INSERT INTO recent_partners(user_id,partner_id,last_chat_at)
            VALUES (1,3,'2026-08-10T10:00:00'),(1,2,'2026-08-10T11:00:00');
            """
        )
        await conn.commit()


@pytest.mark.asyncio
async def test_latest_partner_remains_authorized_after_active_chat_is_gone(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "reveal.db")
    await _create_reveal_db(db_path)
    monkeypatch.setattr(social_repository, "DB_PATH", db_path)

    assert await social_repository.is_latest_partner(1, 2)
    assert not await social_repository.is_latest_partner(1, 3)


@pytest.mark.asyncio
async def test_chat_reveal_payment_is_atomic_and_idempotent(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "reveal-payment.db")
    await _create_reveal_db(db_path)
    monkeypatch.setattr(chat_reveal_repository, "DB_PATH", db_path)

    assert await chat_reveal_repository.apply_chat_reveal_payment(
        charge_id="charge-1",
        buyer_id=1,
        partner_id=2,
        amount=100,
    )
    assert not await chat_reveal_repository.apply_chat_reveal_payment(
        charge_id="charge-1",
        buyer_id=1,
        partner_id=2,
        amount=100,
    )

    async with aiosqlite.connect(db_path) as conn:
        spent = await (await conn.execute(
            "SELECT total_stars_spent FROM users WHERE user_id=1"
        )).fetchone()
        purchases = await (await conn.execute(
            "SELECT COUNT(*) FROM purchases WHERE type='reveal'"
        )).fetchone()
    assert spent == (100,)
    assert purchases == (1,)


@pytest.mark.asyncio
async def test_chat_reveal_payment_rejects_stale_partner_without_side_effects(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "stale-reveal.db")
    await _create_reveal_db(db_path)
    monkeypatch.setattr(chat_reveal_repository, "DB_PATH", db_path)

    with pytest.raises(ValueError, match="latest matched partner"):
        await chat_reveal_repository.apply_chat_reveal_payment(
            charge_id="charge-stale",
            buyer_id=1,
            partner_id=3,
            amount=100,
        )

    async with aiosqlite.connect(db_path) as conn:
        spent = await (await conn.execute(
            "SELECT total_stars_spent FROM users WHERE user_id=1"
        )).fetchone()
        purchases = await (await conn.execute("SELECT COUNT(*) FROM purchases")).fetchone()
    assert spent == (0,)
    assert purchases == (0,)


@pytest.mark.asyncio
async def test_precheckout_reveal_uses_latest_partner_not_active_chat(monkeypatch) -> None:
    monkeypatch.setattr(payment_guard.db, "get_setting", AsyncMock(return_value="100"))
    monkeypatch.setattr(payment_guard.db, "is_latest_partner", AsyncMock(return_value=True))
    get_partner = AsyncMock(return_value=None)
    monkeypatch.setattr(payment_guard.db, "get_partner", get_partner)

    assert await payment_guard._validate_payload(1, "reveal_2", 100) is None
    get_partner.assert_not_awaited()

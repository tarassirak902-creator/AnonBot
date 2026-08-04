from __future__ import annotations

from datetime import datetime

import aiosqlite
import pytest

from app.database import payment_operations


async def _create_schema(path: str) -> None:
    async with aiosqlite.connect(path) as conn:
        await conn.executescript(
            """
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                total_stars_spent INTEGER DEFAULT 0,
                stars_balance INTEGER DEFAULT 0,
                sent_gifts INTEGER DEFAULT 0,
                received_gifts INTEGER DEFAULT 0,
                is_vip INTEGER DEFAULT 0,
                vip_expires_at TEXT
            );
            CREATE TABLE gifts (
                id INTEGER PRIMARY KEY,
                name TEXT,
                emoji TEXT,
                price_stars INTEGER
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
            CREATE TABLE anonymous_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                public_id TEXT UNIQUE,
                sender_id INTEGER NOT NULL,
                receiver_id INTEGER NOT NULL,
                author_revealed INTEGER DEFAULT 0
            );
            INSERT INTO users(user_id) VALUES (1), (2);
            INSERT INTO gifts(id,name,emoji,price_stars) VALUES (7,'Rose','🌹',50);
            INSERT INTO anonymous_questions(public_id,sender_id,receiver_id)
            VALUES ('question-1',2,1);
            """
        )
        await conn.commit()


@pytest.mark.asyncio
async def test_question_stars_is_atomic_and_idempotent(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "payments.db")
    await _create_schema(db_path)
    monkeypatch.setattr(payment_operations, "DB_PATH", db_path)

    assert await payment_operations.apply_question_stars_payment(
        charge_id="charge-stars-1", buyer_id=1, receiver_id=2, amount=50
    )
    assert not await payment_operations.apply_question_stars_payment(
        charge_id="charge-stars-1", buyer_id=1, receiver_id=2, amount=50
    )

    async with aiosqlite.connect(db_path) as conn:
        buyer = await (await conn.execute(
            "SELECT total_stars_spent FROM users WHERE user_id=1"
        )).fetchone()
        receiver = await (await conn.execute(
            "SELECT stars_balance FROM users WHERE user_id=2"
        )).fetchone()
        purchases = await (await conn.execute(
            "SELECT COUNT(*) FROM purchases WHERE telegram_payment_charge_id='charge-stars-1'"
        )).fetchone()

    assert buyer[0] == 50
    assert receiver[0] == 50
    assert purchases[0] == 1


@pytest.mark.asyncio
async def test_question_stars_rolls_back_when_receiver_missing(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "payments.db")
    await _create_schema(db_path)
    monkeypatch.setattr(payment_operations, "DB_PATH", db_path)

    with pytest.raises(ValueError):
        await payment_operations.apply_question_stars_payment(
            charge_id="charge-missing", buyer_id=1, receiver_id=999, amount=50
        )

    async with aiosqlite.connect(db_path) as conn:
        buyer = await (await conn.execute(
            "SELECT total_stars_spent FROM users WHERE user_id=1"
        )).fetchone()
        purchases = await (await conn.execute("SELECT COUNT(*) FROM purchases")).fetchone()

    assert buyer[0] == 0
    assert purchases[0] == 0


@pytest.mark.asyncio
async def test_vip_extension_and_purchase_are_one_transaction(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "payments.db")
    await _create_schema(db_path)
    monkeypatch.setattr(payment_operations, "DB_PATH", db_path)

    assert await payment_operations.apply_vip_payment(
        charge_id="charge-vip-1",
        buyer_id=1,
        receiver_id=2,
        amount=100,
        days=30,
        purchase_type="question_vip",
    )

    async with aiosqlite.connect(db_path) as conn:
        receiver = await (await conn.execute(
            "SELECT is_vip,vip_expires_at FROM users WHERE user_id=2"
        )).fetchone()
        buyer = await (await conn.execute(
            "SELECT total_stars_spent FROM users WHERE user_id=1"
        )).fetchone()
        purchase = await (await conn.execute(
            "SELECT type,price_stars FROM purchases "
            "WHERE telegram_payment_charge_id='charge-vip-1'"
        )).fetchone()

    assert receiver[0] == 1
    assert datetime.fromisoformat(receiver[1]) > datetime.now()
    assert buyer[0] == 100
    assert purchase == ("question_vip", 100)


@pytest.mark.asyncio
async def test_gift_updates_both_users_and_purchase_once(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "payments.db")
    await _create_schema(db_path)
    monkeypatch.setattr(payment_operations, "DB_PATH", db_path)

    assert await payment_operations.apply_gift_payment(
        charge_id="charge-gift-1",
        buyer_id=1,
        receiver_id=2,
        gift_id=7,
        amount=50,
        purchase_type="question_gift",
    )
    assert not await payment_operations.apply_gift_payment(
        charge_id="charge-gift-1",
        buyer_id=1,
        receiver_id=2,
        gift_id=7,
        amount=50,
        purchase_type="question_gift",
    )

    async with aiosqlite.connect(db_path) as conn:
        buyer = await (await conn.execute(
            "SELECT sent_gifts,total_stars_spent FROM users WHERE user_id=1"
        )).fetchone()
        receiver = await (await conn.execute(
            "SELECT received_gifts FROM users WHERE user_id=2"
        )).fetchone()
        purchase_count = await (await conn.execute(
            "SELECT COUNT(*) FROM purchases WHERE telegram_payment_charge_id='charge-gift-1'"
        )).fetchone()

    assert buyer == (1, 50)
    assert receiver == (1,)
    assert purchase_count == (1,)


@pytest.mark.asyncio
async def test_question_reveal_is_atomic_and_cannot_be_bought_twice(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "payments.db")
    await _create_schema(db_path)
    monkeypatch.setattr(payment_operations, "DB_PATH", db_path)

    sender_id = await payment_operations.apply_question_reveal_payment(
        charge_id="charge-reveal-1",
        buyer_id=1,
        public_id="question-1",
        amount=100,
    )
    assert sender_id == 2

    with pytest.raises(ValueError):
        await payment_operations.apply_question_reveal_payment(
            charge_id="charge-reveal-2",
            buyer_id=1,
            public_id="question-1",
            amount=100,
        )

    async with aiosqlite.connect(db_path) as conn:
        question = await (await conn.execute(
            "SELECT author_revealed FROM anonymous_questions WHERE public_id='question-1'"
        )).fetchone()
        buyer = await (await conn.execute(
            "SELECT total_stars_spent FROM users WHERE user_id=1"
        )).fetchone()
        purchases = await (await conn.execute(
            "SELECT COUNT(*) FROM purchases WHERE type='question_reveal'"
        )).fetchone()

    assert question == (1,)
    assert buyer == (100,)
    assert purchases == (1,)

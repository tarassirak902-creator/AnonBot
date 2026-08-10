from __future__ import annotations

import asyncio

import aiosqlite
import pytest

from app.database import balance_repository


async def _create_balance_db(path: str, *, balance: int = 100) -> None:
    async with aiosqlite.connect(path) as conn:
        await conn.execute(
            "CREATE TABLE users (user_id INTEGER PRIMARY KEY, stars_balance INTEGER DEFAULT 0)"
        )
        await conn.execute(
            "CREATE TABLE withdraw_requests ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,amount INTEGER,"
            "status TEXT,timestamp TEXT)"
        )
        await conn.execute("INSERT INTO users(user_id,stars_balance) VALUES (1,?)", (balance,))
        await conn.commit()


@pytest.mark.asyncio
async def test_concurrent_balance_deduction_cannot_overspend(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "balance.db")
    monkeypatch.setattr(balance_repository, "DB_PATH", db_path)
    await _create_balance_db(db_path)

    results = await asyncio.gather(
        balance_repository.deduct_user_balance(1, 80),
        balance_repository.deduct_user_balance(1, 80),
    )

    assert sorted(results) == [False, True]
    async with aiosqlite.connect(db_path) as conn:
        row = await (await conn.execute("SELECT stars_balance FROM users WHERE user_id=1")).fetchone()
    assert row == (20,)


@pytest.mark.asyncio
@pytest.mark.parametrize("amount", [0, -1, -100])
async def test_non_positive_deduction_is_rejected(tmp_path, monkeypatch, amount: int) -> None:
    db_path = str(tmp_path / "balance-invalid.db")
    monkeypatch.setattr(balance_repository, "DB_PATH", db_path)
    await _create_balance_db(db_path)

    assert not await balance_repository.deduct_user_balance(1, amount)
    async with aiosqlite.connect(db_path) as conn:
        row = await (await conn.execute("SELECT stars_balance FROM users WHERE user_id=1")).fetchone()
    assert row == (100,)


@pytest.mark.asyncio
@pytest.mark.parametrize("amount", [0, -1, -100])
async def test_non_positive_withdrawal_cannot_credit_balance(tmp_path, monkeypatch, amount: int) -> None:
    db_path = str(tmp_path / "withdraw-invalid.db")
    monkeypatch.setattr(balance_repository, "DB_PATH", db_path)
    await _create_balance_db(db_path)

    assert await balance_repository.create_withdraw_request_atomic(1, amount) is None
    async with aiosqlite.connect(db_path) as conn:
        balance = await (await conn.execute("SELECT stars_balance FROM users WHERE user_id=1")).fetchone()
        requests = await (await conn.execute("SELECT COUNT(*) FROM withdraw_requests")).fetchone()
    assert balance == (100,)
    assert requests == (0,)


@pytest.mark.asyncio
async def test_concurrent_withdrawals_reserve_balance_once(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "withdraw-race.db")
    monkeypatch.setattr(balance_repository, "DB_PATH", db_path)
    await _create_balance_db(db_path)

    request_ids = await asyncio.gather(
        balance_repository.create_withdraw_request_atomic(1, 80),
        balance_repository.create_withdraw_request_atomic(1, 80),
    )

    assert sum(request_id is not None for request_id in request_ids) == 1
    async with aiosqlite.connect(db_path) as conn:
        balance = await (await conn.execute("SELECT stars_balance FROM users WHERE user_id=1")).fetchone()
        requests = await (await conn.execute("SELECT amount FROM withdraw_requests")).fetchall()
    assert balance == (20,)
    assert requests == [(80,)]

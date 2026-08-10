from __future__ import annotations

import asyncio

import aiosqlite
import pytest

from app.database import balance_repository


@pytest.mark.asyncio
async def test_concurrent_balance_deduction_cannot_overspend(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "balance.db")
    monkeypatch.setattr(balance_repository, "DB_PATH", db_path)

    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "CREATE TABLE users (user_id INTEGER PRIMARY KEY, stars_balance INTEGER DEFAULT 0)"
        )
        await conn.execute("INSERT INTO users(user_id,stars_balance) VALUES (1,100)")
        await conn.commit()

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
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "CREATE TABLE users (user_id INTEGER PRIMARY KEY, stars_balance INTEGER DEFAULT 0)"
        )
        await conn.execute("INSERT INTO users(user_id,stars_balance) VALUES (1,100)")
        await conn.commit()

    assert not await balance_repository.deduct_user_balance(1, amount)
    async with aiosqlite.connect(db_path) as conn:
        row = await (await conn.execute("SELECT stars_balance FROM users WHERE user_id=1")).fetchone()
    assert row == (100,)

from __future__ import annotations

import asyncio

import aiosqlite
import pytest

from app.database import duel_repository


@pytest.mark.asyncio
async def test_only_one_concurrent_duel_claim_succeeds(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "duels.db"
    monkeypatch.setattr(duel_repository, "DB_PATH", str(db_path))

    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(
            """
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                stars_balance INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE game_duels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id INTEGER NOT NULL,
                partner_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'waiting',
                game_type TEXT NOT NULL DEFAULT 'darts'
            );
            INSERT INTO users(user_id) VALUES (1), (2);
            INSERT INTO game_duels(creator_id,partner_id,amount,status,game_type)
            VALUES (1,2,100,'waiting','darts');
            """
        )
        await conn.commit()

    first, second = await asyncio.gather(
        duel_repository.claim_waiting_duel(1, 2, 100),
        duel_repository.claim_waiting_duel(1, 2, 100),
    )
    assert sum(result is not None for result in (first, second)) == 1


@pytest.mark.asyncio
async def test_duel_settlement_is_idempotent(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "settlement.db"
    monkeypatch.setattr(duel_repository, "DB_PATH", str(db_path))

    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(
            """
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                stars_balance INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE game_duels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id INTEGER NOT NULL,
                partner_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                status TEXT NOT NULL,
                game_type TEXT NOT NULL
            );
            INSERT INTO users(user_id) VALUES (1), (2);
            INSERT INTO game_duels(creator_id,partner_id,amount,status,game_type)
            VALUES (1,2,100,'active','darts');
            """
        )
        await conn.commit()

    assert await duel_repository.settle_active_duel(1, 1) == 180
    assert await duel_repository.settle_active_duel(1, 1) is None

    async with aiosqlite.connect(db_path) as conn:
        balance = (
            await (await conn.execute("SELECT stars_balance FROM users WHERE user_id=1")).fetchone()
        )[0]
        status = (
            await (await conn.execute("SELECT status FROM game_duels WHERE id=1")).fetchone()
        )[0]
    assert balance == 180
    assert status == "completed"

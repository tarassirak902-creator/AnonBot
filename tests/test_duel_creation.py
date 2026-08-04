from __future__ import annotations

import asyncio

import aiosqlite
import pytest

from app.database import duel_repository


async def _create_schema(path: str) -> None:
    async with aiosqlite.connect(path) as conn:
        await conn.executescript(
            """
            CREATE TABLE active_chats (
                user_id INTEGER PRIMARY KEY,
                partner_id INTEGER NOT NULL,
                created_at TEXT
            );
            CREATE TABLE game_duels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id INTEGER,
                partner_id INTEGER,
                amount INTEGER,
                status TEXT DEFAULT 'waiting',
                game_type TEXT DEFAULT 'darts'
            );
            INSERT INTO active_chats(user_id,partner_id) VALUES (1,2),(2,1);
            """
        )
        await conn.commit()


@pytest.mark.asyncio
async def test_only_one_duel_for_pair_can_be_created_concurrently(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "duel-create.db")
    await _create_schema(db_path)
    monkeypatch.setattr(duel_repository, "DB_PATH", db_path)

    first, second = await asyncio.gather(
        duel_repository.create_waiting_duel_from_payment(
            charge_id="charge-a", creator_id=1, partner_id=2, amount=100, game_type="darts"
        ),
        duel_repository.create_waiting_duel_from_payment(
            charge_id="charge-b", creator_id=2, partner_id=1, amount=100, game_type="darts"
        ),
    )
    assert sum(result is not None for result in (first, second)) == 1

    async with aiosqlite.connect(db_path) as conn:
        count = await (await conn.execute(
            "SELECT COUNT(*) FROM game_duels WHERE status='waiting'"
        )).fetchone()
    assert count == (1,)


@pytest.mark.asyncio
async def test_same_charge_cannot_create_second_duel(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "duel-charge.db")
    await _create_schema(db_path)
    monkeypatch.setattr(duel_repository, "DB_PATH", db_path)

    duel_id = await duel_repository.create_waiting_duel_from_payment(
        charge_id="charge-same", creator_id=1, partner_id=2, amount=50, game_type="basketball"
    )
    assert duel_id is not None
    assert await duel_repository.create_waiting_duel_from_payment(
        charge_id="charge-same", creator_id=1, partner_id=2, amount=50, game_type="basketball"
    ) is None


@pytest.mark.asyncio
async def test_duel_is_rejected_after_chat_ends(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "duel-ended.db")
    await _create_schema(db_path)
    monkeypatch.setattr(duel_repository, "DB_PATH", db_path)

    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("DELETE FROM active_chats")
        await conn.commit()

    assert await duel_repository.create_waiting_duel_from_payment(
        charge_id="charge-ended", creator_id=1, partner_id=2, amount=50, game_type="darts"
    ) is None

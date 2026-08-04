from __future__ import annotations

import asyncio

import aiosqlite
import pytest

from app.database import matchmaking_repository


async def _create_schema(path: str) -> None:
    async with aiosqlite.connect(path) as conn:
        await conn.executescript(
            """
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                blocked INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE queues (
                user_id INTEGER PRIMARY KEY,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE active_chats (
                user_id INTEGER PRIMARY KEY,
                partner_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO users(user_id) VALUES (1),(2),(3),(4);
            """
        )
        await conn.commit()


@pytest.mark.asyncio
async def test_concurrent_matchmaking_creates_disjoint_pairs(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "matchmaking.db")
    await _create_schema(db_path)
    monkeypatch.setattr(matchmaking_repository, "DB_PATH", db_path)

    await asyncio.gather(
        *(matchmaking_repository.try_match_user(user_id) for user_id in (1, 2, 3, 4))
    )

    async with aiosqlite.connect(db_path) as conn:
        rows = await (
            await conn.execute(
                "SELECT user_id,partner_id FROM active_chats ORDER BY user_id"
            )
        ).fetchall()
        queued = await (await conn.execute("SELECT COUNT(*) FROM queues")).fetchone()

    assert len(rows) == 4
    mapping = dict(rows)
    assert set(mapping) == {1, 2, 3, 4}
    assert all(mapping.get(partner) == user for user, partner in rows)
    assert len({frozenset((user, partner)) for user, partner in rows}) == 2
    assert queued == (0,)


@pytest.mark.asyncio
async def test_three_concurrent_users_create_one_pair_and_one_waiter(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "three-users.db")
    await _create_schema(db_path)
    monkeypatch.setattr(matchmaking_repository, "DB_PATH", db_path)

    await asyncio.gather(
        *(matchmaking_repository.try_match_user(user_id) for user_id in (1, 2, 3))
    )

    async with aiosqlite.connect(db_path) as conn:
        rows = await (
            await conn.execute("SELECT user_id,partner_id FROM active_chats")
        ).fetchall()
        queued = await (
            await conn.execute("SELECT user_id FROM queues")
        ).fetchall()

    assert len(rows) == 2
    mapping = dict(rows)
    assert all(mapping.get(partner) == user for user, partner in rows)
    assert len(queued) == 1
    assert queued[0][0] not in mapping


@pytest.mark.asyncio
async def test_repeated_join_preserves_fifo_position(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "fifo.db")
    await _create_schema(db_path)
    monkeypatch.setattr(matchmaking_repository, "DB_PATH", db_path)

    assert await matchmaking_repository.try_match_user(1) is None
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "UPDATE queues SET created_at='2020-01-01 00:00:00' WHERE user_id=1"
        )
        await conn.execute(
            "INSERT INTO queues(user_id,created_at) VALUES (2,'2021-01-01 00:00:00')"
        )
        await conn.commit()

    assert await matchmaking_repository.try_match_user(1) == 2


@pytest.mark.asyncio
async def test_candidate_referenced_by_orphan_chat_is_not_selected(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "orphan.db")
    await _create_schema(db_path)
    monkeypatch.setattr(matchmaking_repository, "DB_PATH", db_path)

    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("INSERT INTO queues(user_id) VALUES (2),(3)")
        await conn.execute(
            "INSERT INTO active_chats(user_id,partner_id) VALUES (4,2)"
        )
        await conn.commit()

    partner = await matchmaking_repository.try_match_user(1)
    assert partner == 3

    async with aiosqlite.connect(db_path) as conn:
        rows = await (
            await conn.execute(
                "SELECT user_id,partner_id FROM active_chats ORDER BY user_id"
            )
        ).fetchall()

    assert (1, 3) in rows and (3, 1) in rows
    assert (4, 2) in rows


@pytest.mark.asyncio
async def test_blocked_user_is_removed_from_queue(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "blocked.db")
    await _create_schema(db_path)
    monkeypatch.setattr(matchmaking_repository, "DB_PATH", db_path)

    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("UPDATE users SET blocked=1 WHERE user_id=1")
        await conn.execute("INSERT INTO queues(user_id) VALUES (1)")
        await conn.commit()

    assert await matchmaking_repository.try_match_user(1) is None

    async with aiosqlite.connect(db_path) as conn:
        queued = await (
            await conn.execute("SELECT COUNT(*) FROM queues WHERE user_id=1")
        ).fetchone()
    assert queued == (0,)

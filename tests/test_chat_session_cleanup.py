from __future__ import annotations

import aiosqlite
import pytest

from app.database import chat_session_repository


async def _create_db(path: str) -> None:
    async with aiosqlite.connect(path) as conn:
        await conn.executescript(
            """
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                current_chat_start TEXT
            );
            CREATE TABLE active_chats (
                user_id INTEGER PRIMARY KEY,
                partner_id INTEGER NOT NULL,
                created_at TEXT
            );
            CREATE TABLE queues (
                user_id INTEGER PRIMARY KEY,
                created_at TEXT
            );
            INSERT INTO users(user_id,current_chat_start)
            VALUES (1,'2026-08-11T10:00:00'),(2,'2026-08-11T10:00:00');
            INSERT INTO active_chats(user_id,partner_id,created_at)
            VALUES (1,2,CURRENT_TIMESTAMP),(2,1,CURRENT_TIMESTAMP);
            INSERT INTO queues(user_id,created_at) VALUES (2,CURRENT_TIMESTAMP);
            """
        )
        await conn.commit()


@pytest.mark.asyncio
async def test_end_chat_clears_both_session_markers_and_pair(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "chat.db")
    await _create_db(db_path)
    monkeypatch.setattr(chat_session_repository, "DB_PATH", db_path)

    assert await chat_session_repository.end_chat(1) == 2

    async with aiosqlite.connect(db_path) as conn:
        sessions = await (
            await conn.execute(
                "SELECT user_id,current_chat_start FROM users ORDER BY user_id"
            )
        ).fetchall()
        active = await (await conn.execute("SELECT COUNT(*) FROM active_chats")).fetchone()
        queued = await (await conn.execute("SELECT COUNT(*) FROM queues")).fetchone()

    assert sessions == [(1, None), (2, None)]
    assert active == (0,)
    assert queued == (0,)


@pytest.mark.asyncio
async def test_end_chat_without_active_pair_still_clears_stale_session(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "stale.db")
    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(
            """
            CREATE TABLE users (user_id INTEGER PRIMARY KEY, current_chat_start TEXT);
            CREATE TABLE active_chats (user_id INTEGER PRIMARY KEY, partner_id INTEGER NOT NULL);
            CREATE TABLE queues (user_id INTEGER PRIMARY KEY, created_at TEXT);
            INSERT INTO users(user_id,current_chat_start) VALUES (1,'2026-08-11T10:00:00');
            INSERT INTO queues(user_id,created_at) VALUES (1,CURRENT_TIMESTAMP);
            """
        )
        await conn.commit()
    monkeypatch.setattr(chat_session_repository, "DB_PATH", db_path)

    assert await chat_session_repository.end_chat(1) is None

    async with aiosqlite.connect(db_path) as conn:
        session = await (
            await conn.execute("SELECT current_chat_start FROM users WHERE user_id=1")
        ).fetchone()
        queued = await (await conn.execute("SELECT COUNT(*) FROM queues")).fetchone()

    assert session == (None,)
    assert queued == (0,)

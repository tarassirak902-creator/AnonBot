from __future__ import annotations

import aiosqlite
import pytest

from app.database import schema_migrations


@pytest.mark.asyncio
async def test_safe_init_preserves_legacy_matchmaking_rows(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "legacy.db")
    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(
            """
            CREATE TABLE queues (
                user_id INTEGER PRIMARY KEY,
                chat_type TEXT,
                created_at TEXT
            );
            CREATE TABLE active_chats (
                user_id INTEGER PRIMARY KEY,
                partner_id INTEGER,
                chat_type TEXT,
                created_at TEXT
            );
            INSERT INTO queues VALUES (10, 'random', '2026-01-01T10:00:00');
            INSERT INTO active_chats VALUES (10, 20, 'random', '2026-01-01T10:01:00');
            """
        )
        await conn.commit()

    async def destructive_legacy_init() -> None:
        async with aiosqlite.connect(db_path) as conn:
            await conn.executescript(
                """
                DROP TABLE queues;
                CREATE TABLE queues (
                    user_id INTEGER PRIMARY KEY,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                DROP TABLE active_chats;
                CREATE TABLE active_chats (
                    user_id INTEGER PRIMARY KEY,
                    partner_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            await conn.commit()

    monkeypatch.setattr(schema_migrations, "DB_PATH", db_path)
    monkeypatch.setattr(schema_migrations.legacy_repository, "init_db", destructive_legacy_init)

    await schema_migrations.init_db()

    async with aiosqlite.connect(db_path) as conn:
        queue = await (await conn.execute(
            "SELECT user_id,created_at FROM queues"
        )).fetchone()
        chat = await (await conn.execute(
            "SELECT user_id,partner_id,created_at FROM active_chats"
        )).fetchone()
        migration = await (await conn.execute(
            "SELECT MAX(version) FROM schema_migrations"
        )).fetchone()

    assert queue == (10, "2026-01-01T10:00:00")
    assert chat == (10, 20, "2026-01-01T10:01:00")
    assert migration == (schema_migrations.CURRENT_SCHEMA_VERSION,)


@pytest.mark.asyncio
async def test_safe_init_is_repeatable(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "repeatable.db")
    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(
            """
            CREATE TABLE queues (
                user_id INTEGER PRIMARY KEY,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE active_chats (
                user_id INTEGER PRIMARY KEY,
                partner_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO queues(user_id) VALUES (1);
            """
        )
        await conn.commit()

    async def noop_legacy_init() -> None:
        return None

    monkeypatch.setattr(schema_migrations, "DB_PATH", db_path)
    monkeypatch.setattr(schema_migrations.legacy_repository, "init_db", noop_legacy_init)

    await schema_migrations.init_db()
    await schema_migrations.init_db()

    async with aiosqlite.connect(db_path) as conn:
        queues = await (await conn.execute("SELECT COUNT(*) FROM queues")).fetchone()
        versions = await (await conn.execute("SELECT COUNT(*) FROM schema_migrations")).fetchone()
        max_version = await (await conn.execute("SELECT MAX(version) FROM schema_migrations")).fetchone()

    assert queues == (1,)
    assert versions == (schema_migrations.CURRENT_SCHEMA_VERSION,)
    assert max_version == (schema_migrations.CURRENT_SCHEMA_VERSION,)

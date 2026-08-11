from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import aiosqlite
import pytest

from app.database import chat_session_repository
from app.services import matchmaking_service
from app.services.database_backup import create_database_backup
from tools.validate_db_copy import _online_sqlite_copy


@pytest.mark.asyncio
async def test_recovery_clears_session_markers_for_broken_chat(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "bot.db"
    async with aiosqlite.connect(db_path) as conn:
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
            INSERT INTO users VALUES (1, '2026-08-11T10:00:00');
            INSERT INTO users VALUES (2, '2026-08-11T10:00:00');
            INSERT INTO active_chats VALUES (1, 2, CURRENT_TIMESTAMP);
            INSERT INTO queues VALUES (2, CURRENT_TIMESTAMP);
            """
        )
        await conn.commit()

    monkeypatch.setattr(matchmaking_service, "DB_PATH", str(db_path))
    repaired = await matchmaking_service.recover_matchmaking_state()
    assert repaired >= 1

    async with aiosqlite.connect(db_path) as conn:
        chats = await (await conn.execute("SELECT COUNT(*) FROM active_chats")).fetchone()
        markers = await (await conn.execute(
            "SELECT user_id,current_chat_start FROM users ORDER BY user_id"
        )).fetchall()
        queues = await (await conn.execute("SELECT COUNT(*) FROM queues")).fetchone()

    assert chats == (0,)
    assert markers == [(1, None), (2, None)]
    assert queues == (0,)


@pytest.mark.asyncio
async def test_atomic_timeout_refuses_stale_pair(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "bot.db"
    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(
            """
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                chat_time_seconds INTEGER DEFAULT 0,
                completed_dialogs INTEGER DEFAULT 0,
                current_chat_start TEXT,
                last_activity TEXT
            );
            CREATE TABLE active_chats (
                user_id INTEGER PRIMARY KEY,
                partner_id INTEGER NOT NULL,
                created_at TEXT
            );
            CREATE TABLE queues (user_id INTEGER PRIMARY KEY, created_at TEXT);
            INSERT INTO users VALUES (1,0,0,'2026-08-11T10:00:00',NULL);
            INSERT INTO users VALUES (2,0,0,'2026-08-11T10:00:00',NULL);
            INSERT INTO users VALUES (3,0,0,'2026-08-11T10:00:00',NULL);
            INSERT INTO active_chats VALUES (1,3,CURRENT_TIMESTAMP);
            INSERT INTO active_chats VALUES (3,1,CURRENT_TIMESTAMP);
            """
        )
        await conn.commit()

    monkeypatch.setattr(chat_session_repository, "DB_PATH", str(db_path))
    expired = await chat_session_repository.expire_chat_pair_if_active(1, 2)
    assert expired is False

    async with aiosqlite.connect(db_path) as conn:
        pair = await (await conn.execute(
            "SELECT user_id,partner_id FROM active_chats ORDER BY user_id"
        )).fetchall()
        user1 = await (await conn.execute(
            "SELECT chat_time_seconds,completed_dialogs,current_chat_start FROM users WHERE user_id=1"
        )).fetchone()

    assert pair == [(1, 3), (3, 1)]
    assert user1 == (0, 0, "2026-08-11T10:00:00")


@pytest.mark.asyncio
async def test_atomic_timeout_accounts_and_tears_down_current_pair(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "bot.db"
    old = (datetime.now() - timedelta(seconds=90)).isoformat()
    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(
            """
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                chat_time_seconds INTEGER DEFAULT 0,
                completed_dialogs INTEGER DEFAULT 0,
                current_chat_start TEXT,
                last_activity TEXT
            );
            CREATE TABLE active_chats (
                user_id INTEGER PRIMARY KEY,
                partner_id INTEGER NOT NULL,
                created_at TEXT
            );
            CREATE TABLE queues (user_id INTEGER PRIMARY KEY, created_at TEXT);
            """
        )
        await conn.executemany(
            "INSERT INTO users(user_id,current_chat_start) VALUES (?,?)",
            [(1, old), (2, old)],
        )
        await conn.executemany(
            "INSERT INTO active_chats(user_id,partner_id,created_at) VALUES (?,?,CURRENT_TIMESTAMP)",
            [(1, 2), (2, 1)],
        )
        await conn.commit()

    monkeypatch.setattr(chat_session_repository, "DB_PATH", str(db_path))
    expired = await chat_session_repository.expire_chat_pair_if_active(1, 2)
    assert expired is True

    async with aiosqlite.connect(db_path) as conn:
        rows = await (await conn.execute(
            "SELECT chat_time_seconds,completed_dialogs,current_chat_start FROM users ORDER BY user_id"
        )).fetchall()
        chats = await (await conn.execute("SELECT COUNT(*) FROM active_chats")).fetchone()

    assert all(row[0] >= 60 and row[1] == 1 and row[2] is None for row in rows)
    assert chats == (0,)


def test_backup_records_audit_row(tmp_path: Path) -> None:
    db_path = tmp_path / "bot.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE users(user_id INTEGER PRIMARY KEY)")
        conn.commit()

    result = create_database_backup(source=db_path, backup_dir=tmp_path / "backups")
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT path,size_bytes,integrity FROM backup_audit ORDER BY id DESC LIMIT 1"
        ).fetchone()

    assert row == (str(result.path), result.size_bytes, "ok")


def test_online_copy_includes_committed_wal_state(tmp_path: Path) -> None:
    source = tmp_path / "live.db"
    destination = tmp_path / "copy.db"
    with sqlite3.connect(source) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA wal_autocheckpoint=0")
        conn.execute("CREATE TABLE events(id INTEGER PRIMARY KEY, value TEXT)")
        conn.commit()
        conn.execute("INSERT INTO events(value) VALUES ('committed-in-wal')")
        conn.commit()
        _online_sqlite_copy(source, destination)

    with sqlite3.connect(destination) as copied:
        assert copied.execute("SELECT value FROM events").fetchone() == ("committed-in-wal",)


def test_fsm_amount_handlers_do_not_require_text_messages() -> None:
    source = (Path(__file__).resolve().parents[1] / "app" / "handlers" / "forms.py").read_text(
        encoding="utf-8"
    )
    assert "message.text.strip()" not in source
    assert source.count('(message.text or "").strip()') >= 4


def test_gift_screen_describes_telegram_stars_payment() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "app" / "handlers" / "user_actions_ui.py"
    ).read_text(encoding="utf-8")
    assert "Оплата проходит через Telegram Stars" in source
    assert "Стоимость будет списана с баланса" not in source


def test_ci_installs_declared_dev_requirements() -> None:
    source = (
        Path(__file__).resolve().parents[1] / ".github" / "workflows" / "quality.yml"
    ).read_text(encoding="utf-8")
    assert "pip install -r requirements-dev.txt" in source
    assert "pip install pytest pytest-asyncio" not in source

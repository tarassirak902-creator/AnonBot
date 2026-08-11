from __future__ import annotations

import sqlite3
from pathlib import Path

import aiosqlite
import pytest

from app.database.schema_migrations import CURRENT_SCHEMA_VERSION, apply_schema_migrations
from app.services import health_service
from app.services.database_backup import create_database_backup


@pytest.mark.asyncio
async def test_schema_migrations_apply_sequentially_and_are_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "bot.db"
    async with aiosqlite.connect(db_path) as conn:
        first = await apply_schema_migrations(conn)
        await conn.commit()
        second = await apply_schema_migrations(conn)
        await conn.commit()
        rows = await (await conn.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        )).fetchall()

    assert first == list(range(1, CURRENT_SCHEMA_VERSION + 1))
    assert second == []
    assert [int(row[0]) for row in rows] == list(range(1, CURRENT_SCHEMA_VERSION + 1))


def test_online_backup_is_integrity_checked_and_rotated(tmp_path: Path) -> None:
    db_path = tmp_path / "bot.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE users(user_id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO users VALUES (1, 'Casper')")
        conn.commit()

    backup_dir = tmp_path / "backups"
    create_database_backup(source=db_path, backup_dir=backup_dir, keep=1)
    second = create_database_backup(source=db_path, backup_dir=backup_dir, keep=1)

    assert second.integrity == "ok"
    assert second.size_bytes > 0
    backups = list(backup_dir.glob("bot-*.db"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as conn:
        assert conn.execute("SELECT name FROM users WHERE user_id=1").fetchone() == ("Casper",)


@pytest.mark.asyncio
async def test_health_reports_database_schema_and_disk(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "bot.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
        conn.execute("INSERT INTO schema_migrations VALUES (?, 'now')", (CURRENT_SCHEMA_VERSION,))
        conn.commit()

    monkeypatch.setattr(health_service, "DB_PATH", str(db_path))
    checks = await health_service.collect_health_checks()
    by_name = {item.name: item for item in checks}

    assert by_name["database"].ok is True
    assert by_name["schema"].ok is True
    assert f"version={CURRENT_SCHEMA_VERSION}/{CURRENT_SCHEMA_VERSION}" == by_name["schema"].detail
    assert "disk" in by_name

import asyncio
import sqlite3
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_four_concurrent_users_form_two_reciprocal_pairs(tmp_path, monkeypatch) -> None:
    from app.database import matchmaking_repository
    from app.services import matchmaking_service

    db_path = str(tmp_path / "matchmaking.db")
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
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

    monkeypatch.setattr(matchmaking_repository, "DB_PATH", db_path)
    monkeypatch.setattr(matchmaking_service, "DB_PATH", db_path)

    results = await asyncio.gather(
        *(matchmaking_service.enqueue_or_match(user_id) for user_id in range(1, 5))
    )
    assert len(results) == 4

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT user_id, partner_id FROM active_chats ORDER BY user_id"
        ).fetchall()
        queued = conn.execute("SELECT COUNT(*) FROM queues").fetchone()[0]

    assert queued == 0
    assert len(rows) == 4
    mapping = dict(rows)
    assert set(mapping) == {1, 2, 3, 4}
    assert all(user_id != partner_id for user_id, partner_id in rows)
    assert all(mapping.get(partner_id) == user_id for user_id, partner_id in rows)
    assert len({frozenset((user_id, partner_id)) for user_id, partner_id in rows}) == 2


def test_admin_health_exposes_safe_matchmaking_recovery() -> None:
    source = Path("app/handlers/activity_health_ui.py").read_text(encoding="utf-8")
    assert 'callback_data="admin_matchmaking_recover"' in source
    assert "recover_matchmaking_state()" in source
    assert "admin_matchmaking_recovery" in source
    assert "История, покупки и контакты не затрагиваются" in source


def test_recovery_adapter_is_installed_before_handlers() -> None:
    source = Path("app/handlers/__init__.py").read_text(encoding="utf-8")
    assert source.index("install_matchmaking_v2()") < source.index("from . import questions")


def test_matchmaking_service_serializes_recovery_and_matching() -> None:
    source = Path("app/services/matchmaking_service.py").read_text(encoding="utf-8")
    assert "_MATCH_LOCK = asyncio.Lock()" in source
    assert "async with _MATCH_LOCK:" in source
    assert '"oldest_wait_seconds"' in source
    assert 'strftime("%Y-%m-%d %H:%M:%S")' in source
    assert "datetime(created_at)<datetime(?)" in source

from datetime import datetime, timedelta
from pathlib import Path

import aiosqlite
import pytest

from app.database import manual_chat_teardown as teardown
from app.database import product_analytics_repository as analytics


async def _create_chat_db(path, *, seconds: int) -> None:
    async with aiosqlite.connect(path) as db:
        await db.executescript(
            """
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                chat_time_seconds INTEGER DEFAULT 0,
                completed_dialogs INTEGER DEFAULT 0,
                current_chat_start TEXT,
                last_activity TEXT
            );
            CREATE TABLE active_chats (user_id INTEGER PRIMARY KEY, partner_id INTEGER);
            CREATE TABLE queues (user_id INTEGER PRIMARY KEY);
            """
        )
        started = (datetime.now() - timedelta(seconds=seconds)).isoformat()
        await db.executemany(
            "INSERT INTO users(user_id,current_chat_start) VALUES (?,?)",
            [(101, started), (202, started)],
        )
        await db.executemany(
            "INSERT INTO active_chats(user_id,partner_id) VALUES (?,?)",
            [(101, 202), (202, 101)],
        )
        await db.commit()


@pytest.mark.asyncio
async def test_manual_teardown_accounts_both_users(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "chat.db"
    await _create_chat_db(db_path, seconds=90)
    monkeypatch.setattr(teardown, "DB_PATH", str(db_path))

    result = await teardown.end_chat_with_accounting(101)
    assert result is not None
    assert result.partner_id == 202
    assert result.user_completed is True
    assert result.partner_completed is True

    async with aiosqlite.connect(db_path) as db:
        rows = await (await db.execute(
            "SELECT user_id,completed_dialogs,chat_time_seconds,current_chat_start FROM users ORDER BY user_id"
        )).fetchall()
        active = await (await db.execute("SELECT COUNT(*) FROM active_chats")).fetchone()

    assert rows[0][1] == 1 and rows[1][1] == 1
    assert rows[0][2] >= 89 and rows[1][2] >= 89
    assert rows[0][3] is None and rows[1][3] is None
    assert active[0] == 0


@pytest.mark.asyncio
async def test_short_dialog_is_not_counted_completed(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "chat.db"
    await _create_chat_db(db_path, seconds=10)
    monkeypatch.setattr(teardown, "DB_PATH", str(db_path))
    result = await teardown.end_chat_with_accounting(101)
    assert result is not None
    assert result.user_completed is False
    assert result.partner_completed is False


@pytest.mark.asyncio
async def test_funnel_counts_unique_users(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "events.db"
    monkeypatch.setattr(analytics, "DB_PATH", str(db_path))
    for event in ("app_start", "search_started", "match_found", "dialog_completed", "search_started"):
        await analytics.record_product_event_safe(1, event)
    for event in ("app_start", "search_started"):
        await analytics.record_product_event_safe(2, event)

    data = await analytics.get_funnel_metrics(7)
    assert data.starts == 2
    assert data.searchers == 2
    assert data.matched == 1
    assert data.completed == 1
    assert data.repeat_searchers == 1


def test_growth_dashboard_points_to_product_funnel() -> None:
    source = Path("app/handlers/platform_growth_ui.py").read_text(encoding="utf-8")
    assert 'text="📈 Воронка"' in source
    assert 'callback_data="admin_product_funnel"' in source


def test_dialog_flow_uses_atomic_two_sided_teardown() -> None:
    source = Path("app/handlers/dialog_ui.py").read_text(encoding="utf-8")
    assert "end_chat_with_accounting(user_id)" in source
    assert "result.partner_completed" in source
    assert "dialog_completed" in source

from __future__ import annotations

from datetime import datetime, timedelta

import aiosqlite
import pytest

from app.services import platform_insights


@pytest.mark.asyncio
async def test_admin_snapshot_uses_joined_date_and_complaints_sent(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "insights.db")
    monkeypatch.setattr(platform_insights, "DB_PATH", db_path)
    recent = datetime.now().isoformat()
    old = (datetime.now() - timedelta(days=10)).isoformat()

    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(
            """
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                joined_date TEXT,
                complaints_sent INTEGER DEFAULT 0
            );
            CREATE TABLE queues (user_id INTEGER PRIMARY KEY);
            CREATE TABLE active_chats (user_id INTEGER PRIMARY KEY, partner_id INTEGER);
            """
        )
        await conn.executemany(
            "INSERT INTO users(user_id,joined_date,complaints_sent) VALUES (?,?,?)",
            [(1, recent, 2), (2, old, 3)],
        )
        await conn.commit()

    snapshot = await platform_insights.load_admin_operational_snapshot()

    assert snapshot["users_24h"] == 1
    assert snapshot["users_7d"] == 1
    assert snapshot["complaints"] == 5

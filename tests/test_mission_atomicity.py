from __future__ import annotations

import aiosqlite
import pytest

from app.database import platform_missions_repository as missions


@pytest.mark.asyncio
async def test_mission_event_rolls_back_when_xp_bundle_fails(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "mission-rollback.db")
    monkeypatch.setattr(missions, "DB_PATH", db_path)

    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "CREATE TABLE users (user_id INTEGER PRIMARY KEY, stars_balance INTEGER DEFAULT 0)"
        )
        await conn.execute("INSERT INTO users(user_id,stars_balance) VALUES (1,0)")
        await conn.commit()

    async def fail_bundle(*args, **kwargs):
        raise RuntimeError("forced reward failure")

    monkeypatch.setattr(missions, "apply_reward_bundle", fail_bundle)

    with pytest.raises(RuntimeError, match="forced reward failure"):
        await missions.record_mission_event(1, "event-1", "dialog")

    async with aiosqlite.connect(db_path) as conn:
        event_count = await (await conn.execute("SELECT COUNT(*) FROM mission_events")).fetchone()
    assert event_count == (0,)


@pytest.mark.asyncio
async def test_mission_event_and_xp_are_committed_once_together(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "mission-success.db")
    monkeypatch.setattr(missions, "DB_PATH", db_path)

    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "CREATE TABLE users (user_id INTEGER PRIMARY KEY, stars_balance INTEGER DEFAULT 0)"
        )
        await conn.execute("INSERT INTO users(user_id,stars_balance) VALUES (1,0)")
        await conn.commit()

    assert await missions.record_mission_event(1, "event-1", "dialog")
    assert not await missions.record_mission_event(1, "event-1", "dialog")

    async with aiosqlite.connect(db_path) as conn:
        event_count = await (await conn.execute("SELECT COUNT(*) FROM mission_events")).fetchone()
        xp = await (await conn.execute("SELECT xp FROM account_progress WHERE user_id=1")).fetchone()
        ledger_count = await (await conn.execute("SELECT COUNT(*) FROM xp_ledger WHERE user_id=1")).fetchone()
    assert event_count == (1,)
    assert xp == (5,)
    assert ledger_count == (1,)

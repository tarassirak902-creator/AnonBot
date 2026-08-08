from __future__ import annotations

from datetime import date, timedelta

import aiosqlite
import pytest

from app.database import platform_growth_repository as growth
from app.database import platform_missions_repository as missions
from app.database import platform_personal_goals_repository as goals
from app.database import platform_progress_repository as progress
from app.database import platform_reactivation_repository as reactivation


async def _create_user(db_path: str, user_id: int = 101) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, stars_balance INTEGER DEFAULT 0)"
        )
        await db.execute("INSERT INTO users(user_id, stars_balance) VALUES (?, 0)", (user_id,))
        await db.commit()


@pytest.mark.asyncio
async def test_weekly_reward_rolls_back_claim_when_credit_fails(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "progress-failure.db")
    monkeypatch.setattr(progress, "DB_PATH", db_path)
    user_id = 101
    week = progress._week_key()
    async with aiosqlite.connect(db_path) as db:
        await progress._ensure_schema(db)
        await db.execute(
            "CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, stars_balance INTEGER DEFAULT 0)"
        )
        await db.execute(
            "INSERT INTO weekly_progress(user_id, week_key, progress) VALUES (?, ?, ?)",
            (user_id, week, progress.WEEKLY_TARGET),
        )
        await db.commit()

    with pytest.raises(RuntimeError):
        await progress.claim_weekly_reward(user_id)

    profile = await progress.get_progress_profile(user_id)
    assert profile.weekly_reward_claimed is False


@pytest.mark.asyncio
async def test_weekly_reward_claim_and_stars_commit_together(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "progress-success.db")
    monkeypatch.setattr(progress, "DB_PATH", db_path)
    user_id = 101
    await _create_user(db_path, user_id)
    week = progress._week_key()
    async with aiosqlite.connect(db_path) as db:
        await progress._ensure_schema(db)
        await db.execute(
            "INSERT INTO weekly_progress(user_id, week_key, progress) VALUES (?, ?, ?)",
            (user_id, week, progress.WEEKLY_TARGET),
        )
        await db.commit()

    assert await progress.claim_weekly_reward(user_id) is True
    assert await progress.claim_weekly_reward(user_id) is False

    async with aiosqlite.connect(db_path) as db:
        row = await (await db.execute(
            "SELECT stars_balance FROM users WHERE user_id=?", (user_id,)
        )).fetchone()
    assert row[0] == progress.WEEKLY_REWARD


@pytest.mark.asyncio
async def test_mission_reward_commits_stars_xp_and_claim_once(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "mission.db")
    monkeypatch.setattr(missions, "DB_PATH", db_path)
    user_id = 202
    await _create_user(db_path, user_id)
    async with aiosqlite.connect(db_path) as db:
        await missions._ensure_schema(db)
        for index in range(missions.MISSION_TARGET):
            await db.execute(
                "INSERT INTO mission_events(user_id, season_key, event_key, event_type) VALUES (?, ?, ?, ?)",
                (user_id, missions.SEASON_KEY, f"event-{index}", "test"),
            )
        await db.commit()

    assert await missions.claim_mission_reward(user_id) is True
    assert await missions.claim_mission_reward(user_id) is False

    async with aiosqlite.connect(db_path) as db:
        stars = await (await db.execute(
            "SELECT stars_balance FROM users WHERE user_id=?", (user_id,)
        )).fetchone()
        xp = await (await db.execute(
            "SELECT xp FROM account_progress WHERE user_id=?", (user_id,)
        )).fetchone()
    assert stars[0] == missions.MISSION_STAR_REWARD
    assert xp[0] == missions.MISSION_XP_REWARD


@pytest.mark.asyncio
async def test_personal_goal_reward_commits_bundle_once(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "goals.db")
    monkeypatch.setattr(goals, "DB_PATH", db_path)
    user_id = 303
    await _create_user(db_path, user_id)
    day = goals._day_key()
    keys = goals._goal_keys(user_id, day)
    async with aiosqlite.connect(db_path) as db:
        await goals._ensure_schema(db)
        await db.execute(
            "INSERT INTO personal_goal_days(user_id, day_key) VALUES (?, ?)",
            (user_id, day),
        )
        for key in keys:
            await db.execute(
                "INSERT INTO personal_goal_events(user_id, day_key, event_key) VALUES (?, ?, ?)",
                (user_id, day, key),
            )
        await db.commit()

    assert await goals.claim_personal_goal_reward(user_id) is True
    assert await goals.claim_personal_goal_reward(user_id) is False

    async with aiosqlite.connect(db_path) as db:
        stars = await (await db.execute(
            "SELECT stars_balance FROM users WHERE user_id=?", (user_id,)
        )).fetchone()
        xp = await (await db.execute(
            "SELECT xp FROM account_progress WHERE user_id=?", (user_id,)
        )).fetchone()
    assert stars[0] == goals.GOAL_REWARD_STARS
    assert xp[0] == goals.GOAL_REWARD_XP


@pytest.mark.asyncio
async def test_daily_reward_commits_streak_and_stars_once(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "daily-success.db")
    monkeypatch.setattr(growth, "DB_PATH", db_path)
    user_id = 404
    await _create_user(db_path, user_id)

    claimed, activity, reward = await growth.claim_daily_activity(user_id)
    assert claimed is True
    assert activity.claimed_today is True
    assert reward > 0

    claimed_again, _, second_reward = await growth.claim_daily_activity(user_id)
    assert claimed_again is False
    assert second_reward == 0

    async with aiosqlite.connect(db_path) as db:
        stars = await (await db.execute(
            "SELECT stars_balance FROM users WHERE user_id=?", (user_id,)
        )).fetchone()
        claims = await (await db.execute(
            "SELECT total_claims FROM daily_activity WHERE user_id=?", (user_id,)
        )).fetchone()
    assert stars[0] == reward
    assert claims[0] == 1


@pytest.mark.asyncio
async def test_daily_reward_rolls_back_activity_when_credit_fails(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "daily-failure.db")
    monkeypatch.setattr(growth, "DB_PATH", db_path)
    user_id = 405
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, stars_balance INTEGER DEFAULT 0)"
        )
        await db.commit()

    with pytest.raises(RuntimeError):
        await growth.claim_daily_activity(user_id)

    activity = await growth.get_daily_activity(user_id)
    assert activity.claimed_today is False
    assert activity.streak == 0


@pytest.mark.asyncio
async def test_comeback_reward_commits_claim_stars_and_xp_once(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "comeback-success.db")
    monkeypatch.setattr(reactivation, "DB_PATH", db_path)
    user_id = 505
    await _create_user(db_path, user_id)
    today = date.today()
    previous = today - timedelta(days=reactivation.COMEBACK_MIN_DAYS)

    async with aiosqlite.connect(db_path) as db:
        await reactivation._ensure_schema(db)
        await db.execute(
            "INSERT INTO reactivation_state(user_id, last_seen_day) VALUES (?, ?)",
            (user_id, today.isoformat()),
        )
        await db.execute(
            "INSERT INTO reactivation_events(user_id, return_day, previous_day, gap_days) VALUES (?, ?, ?, ?)",
            (user_id, today.isoformat(), previous.isoformat(), reactivation.COMEBACK_MIN_DAYS),
        )
        await db.commit()

    assert await reactivation.claim_reactivation_reward(user_id, today=today) is True
    assert await reactivation.claim_reactivation_reward(user_id, today=today) is False

    async with aiosqlite.connect(db_path) as db:
        stars = await (await db.execute(
            "SELECT stars_balance FROM users WHERE user_id=?", (user_id,)
        )).fetchone()
        xp = await (await db.execute(
            "SELECT xp FROM account_progress WHERE user_id=?", (user_id,)
        )).fetchone()
        rewards = await (await db.execute(
            "SELECT COUNT(*) FROM reactivation_rewards WHERE user_id=?", (user_id,)
        )).fetchone()
    assert stars[0] == reactivation.COMEBACK_REWARD_STARS
    assert xp[0] == reactivation.COMEBACK_REWARD_XP
    assert rewards[0] == 1


@pytest.mark.asyncio
async def test_comeback_reward_rolls_back_claim_when_credit_fails(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "comeback-failure.db")
    monkeypatch.setattr(reactivation, "DB_PATH", db_path)
    user_id = 506
    today = date.today()
    previous = today - timedelta(days=reactivation.COMEBACK_MIN_DAYS)

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, stars_balance INTEGER DEFAULT 0)"
        )
        await reactivation._ensure_schema(db)
        await db.execute(
            "INSERT INTO reactivation_events(user_id, return_day, previous_day, gap_days) VALUES (?, ?, ?, ?)",
            (user_id, today.isoformat(), previous.isoformat(), reactivation.COMEBACK_MIN_DAYS),
        )
        await db.commit()

    with pytest.raises(RuntimeError):
        await reactivation.claim_reactivation_reward(user_id, today=today)

    async with aiosqlite.connect(db_path) as db:
        rewards = await (await db.execute(
            "SELECT COUNT(*) FROM reactivation_rewards WHERE user_id=?", (user_id,)
        )).fetchone()
    assert rewards[0] == 0

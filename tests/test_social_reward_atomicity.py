from __future__ import annotations

import aiosqlite
import pytest

from app.database import social_repository


async def _create_social_db(path: str) -> None:
    async with aiosqlite.connect(path) as conn:
        await conn.executescript(
            """
            CREATE TABLE daily_rewards (
                user_id INTEGER PRIMARY KEY,
                last_claim_date TEXT,
                streak INTEGER NOT NULL DEFAULT 0,
                total_claims INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE user_progress (
                user_id INTEGER PRIMARY KEY,
                xp INTEGER NOT NULL DEFAULT 0,
                level INTEGER NOT NULL DEFAULT 1,
                positive_ratings INTEGER NOT NULL DEFAULT 0,
                neutral_ratings INTEGER NOT NULL DEFAULT 0,
                negative_ratings INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        await conn.commit()


@pytest.mark.asyncio
async def test_daily_reward_claim_rolls_back_when_xp_write_fails(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "daily-rollback.db")
    monkeypatch.setattr(social_repository, "DB_PATH", db_path)
    await _create_social_db(db_path)
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "CREATE TRIGGER fail_daily_xp BEFORE INSERT ON user_progress "
            "BEGIN SELECT RAISE(ABORT, 'forced xp failure'); END"
        )
        await conn.commit()

    with pytest.raises(aiosqlite.IntegrityError):
        await social_repository.claim_daily_reward(1)

    async with aiosqlite.connect(db_path) as conn:
        claims = await (await conn.execute("SELECT COUNT(*) FROM daily_rewards")).fetchone()
    assert claims == (0,)


@pytest.mark.asyncio
async def test_daily_reward_claim_and_xp_are_one_shot(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "daily-success.db")
    monkeypatch.setattr(social_repository, "DB_PATH", db_path)
    await _create_social_db(db_path)

    first = await social_repository.claim_daily_reward(1)
    second = await social_repository.claim_daily_reward(1)

    assert first["claimed"] is True
    assert first["reward"] == 10
    assert second["claimed"] is False
    async with aiosqlite.connect(db_path) as conn:
        xp = await (await conn.execute("SELECT xp,level FROM user_progress WHERE user_id=1")).fetchone()
        reward = await (await conn.execute("SELECT total_claims FROM daily_rewards WHERE user_id=1")).fetchone()
    assert xp == (10, 1)
    assert reward == (1,)

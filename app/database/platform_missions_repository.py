from __future__ import annotations

from dataclasses import dataclass

import aiosqlite

from .repository import DB_PATH
from .platform_progress_repository import apply_reward_bundle, ensure_reward_schema, grant_xp_once

SEASON_KEY = "season-2026-summer"
MISSION_TARGET = 10
MISSION_XP_REWARD = 75
MISSION_STAR_REWARD = 25


@dataclass(frozen=True)
class MissionProfile:
    progress: int
    target: int
    completed: bool
    reward_claimed: bool


@dataclass(frozen=True)
class MissionMetrics:
    participants: int
    completed: int
    rewards_claimed: int
    events_7d: int


async def _ensure_schema(db: aiosqlite.Connection) -> None:
    await db.executescript(
        """
        CREATE TABLE IF NOT EXISTS mission_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            season_key TEXT NOT NULL,
            event_key TEXT NOT NULL,
            event_type TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, season_key, event_key)
        );
        CREATE TABLE IF NOT EXISTS mission_rewards (
            user_id INTEGER NOT NULL,
            season_key TEXT NOT NULL,
            reward_claimed INTEGER NOT NULL DEFAULT 0,
            claimed_at TEXT,
            PRIMARY KEY(user_id, season_key)
        );
        """
    )


async def record_mission_event(user_id: int, event_key: str, event_type: str) -> bool:
    event_key = event_key.strip()[:96]
    event_type = event_type.strip()[:32]
    if user_id <= 0 or not event_key or not event_type:
        return False
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        await db.execute("BEGIN IMMEDIATE")
        cur = await db.execute(
            "INSERT OR IGNORE INTO mission_events(user_id, season_key, event_key, event_type) VALUES (?, ?, ?, ?)",
            (user_id, SEASON_KEY, event_key, event_type),
        )
        await db.commit()
    if cur.rowcount == 1:
        await grant_xp_once(user_id, f"mission:{SEASON_KEY}:{event_key}", 5, weekly_increment=1)
        return True
    return False


async def get_mission_profile(user_id: int) -> MissionProfile:
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        count_row = await (await db.execute(
            "SELECT COUNT(*) FROM mission_events WHERE user_id=? AND season_key=?",
            (user_id, SEASON_KEY),
        )).fetchone()
        reward_row = await (await db.execute(
            "SELECT reward_claimed FROM mission_rewards WHERE user_id=? AND season_key=?",
            (user_id, SEASON_KEY),
        )).fetchone()
    progress = min(MISSION_TARGET, int((count_row[0] if count_row else 0) or 0))
    claimed = bool(reward_row[0]) if reward_row else False
    return MissionProfile(progress, MISSION_TARGET, progress >= MISSION_TARGET, claimed)


async def claim_mission_reward(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        await ensure_reward_schema(db)
        await db.execute("BEGIN IMMEDIATE")
        row = await (await db.execute(
            "SELECT COUNT(*) FROM mission_events WHERE user_id=? AND season_key=?",
            (user_id, SEASON_KEY),
        )).fetchone()
        if int((row[0] if row else 0) or 0) < MISSION_TARGET:
            await db.rollback()
            return False
        await db.execute(
            "INSERT OR IGNORE INTO mission_rewards(user_id, season_key) VALUES (?, ?)",
            (user_id, SEASON_KEY),
        )
        cur = await db.execute(
            "UPDATE mission_rewards SET reward_claimed=1, claimed_at=CURRENT_TIMESTAMP WHERE user_id=? AND season_key=? AND reward_claimed=0",
            (user_id, SEASON_KEY),
        )
        if cur.rowcount != 1:
            await db.rollback()
            return False
        try:
            await apply_reward_bundle(
                db,
                user_id,
                stars=MISSION_STAR_REWARD,
                xp_source=f"mission-reward:{SEASON_KEY}",
                xp_amount=MISSION_XP_REWARD,
            )
        except Exception:
            await db.rollback()
            raise
        await db.commit()
        return True


async def get_mission_metrics() -> MissionMetrics:
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        async def scalar(sql: str, params: tuple = ()) -> int:
            row = await (await db.execute(sql, params)).fetchone()
            return int((row[0] if row else 0) or 0)
        participants = await scalar("SELECT COUNT(DISTINCT user_id) FROM mission_events WHERE season_key=?", (SEASON_KEY,))
        completed = await scalar(
            "SELECT COUNT(*) FROM (SELECT user_id FROM mission_events WHERE season_key=? GROUP BY user_id HAVING COUNT(*)>=?)",
            (SEASON_KEY, MISSION_TARGET),
        )
        claimed = await scalar("SELECT COUNT(*) FROM mission_rewards WHERE season_key=? AND reward_claimed=1", (SEASON_KEY,))
        events = await scalar("SELECT COUNT(*) FROM mission_events WHERE season_key=? AND created_at>=datetime('now','-7 day')", (SEASON_KEY,))
    return MissionMetrics(participants, completed, claimed, events)

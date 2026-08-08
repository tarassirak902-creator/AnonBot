from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import aiosqlite

from .repository import DB_PATH
from .platform_progress_repository import apply_reward_bundle


GOAL_REWARD_STARS = 12
GOAL_REWARD_XP = 30
GOAL_COUNT = 3

_GOALS = (
    ("growth_open", "🚀 Открой Центр роста"),
    ("daily_claim", "🎁 Забери ежедневный бонус"),
    ("shop_open", "🏪 Загляни в магазин"),
    ("referral_open", "👥 Открой приглашения"),
    ("missions_open", "🎯 Проверь сезонные задания"),
)


@dataclass(frozen=True)
class PersonalGoal:
    event_key: str
    title: str
    completed: bool


@dataclass(frozen=True)
class PersonalGoalProfile:
    goals: tuple[PersonalGoal, ...]
    completed: int
    target: int
    reward_claimed: bool


@dataclass(frozen=True)
class PersonalGoalMetrics:
    participants_today: int
    completed_today: int
    rewards_today: int
    completion_rate: int


def _day_key(today: date | None = None) -> str:
    return (today or date.today()).isoformat()


def _goal_keys(user_id: int, day_key: str) -> tuple[str, ...]:
    # Stable rotation without collecting behavioural payloads.
    offset = (user_id + sum(ord(ch) for ch in day_key)) % len(_GOALS)
    ordered = _GOALS[offset:] + _GOALS[:offset]
    return tuple(item[0] for item in ordered[:GOAL_COUNT])


async def _ensure_schema(db: aiosqlite.Connection) -> None:
    await db.executescript(
        """
        CREATE TABLE IF NOT EXISTS personal_goal_days (
            user_id INTEGER NOT NULL,
            day_key TEXT NOT NULL,
            reward_claimed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id, day_key)
        );
        CREATE TABLE IF NOT EXISTS personal_goal_events (
            user_id INTEGER NOT NULL,
            day_key TEXT NOT NULL,
            event_key TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id, day_key, event_key)
        );
        """
    )


async def record_personal_goal_event(user_id: int, event_key: str) -> bool:
    if user_id <= 0 or event_key not in {item[0] for item in _GOALS}:
        return False
    day = _day_key()
    if event_key not in _goal_keys(user_id, day):
        return False
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        await db.execute("BEGIN IMMEDIATE")
        await db.execute(
            "INSERT OR IGNORE INTO personal_goal_days(user_id, day_key) VALUES (?, ?)",
            (user_id, day),
        )
        cur = await db.execute(
            "INSERT OR IGNORE INTO personal_goal_events(user_id, day_key, event_key) VALUES (?, ?, ?)",
            (user_id, day, event_key),
        )
        await db.commit()
        return cur.rowcount == 1


async def get_personal_goal_profile(user_id: int) -> PersonalGoalProfile:
    day = _day_key()
    keys = _goal_keys(user_id, day)
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        await db.execute(
            "INSERT OR IGNORE INTO personal_goal_days(user_id, day_key) VALUES (?, ?)",
            (user_id, day),
        )
        await db.commit()
        rows = await (await db.execute(
            "SELECT event_key FROM personal_goal_events WHERE user_id=? AND day_key=?",
            (user_id, day),
        )).fetchall()
        reward_row = await (await db.execute(
            "SELECT reward_claimed FROM personal_goal_days WHERE user_id=? AND day_key=?",
            (user_id, day),
        )).fetchone()
    completed_keys = {str(row[0]) for row in rows}
    title_map = dict(_GOALS)
    goals = tuple(PersonalGoal(key, title_map[key], key in completed_keys) for key in keys)
    completed = sum(1 for goal in goals if goal.completed)
    return PersonalGoalProfile(goals, completed, GOAL_COUNT, bool(reward_row[0]) if reward_row else False)


async def claim_personal_goal_reward(user_id: int) -> bool:
    day = _day_key()
    keys = _goal_keys(user_id, day)
    placeholders = ",".join("?" for _ in keys)
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        await db.execute("BEGIN IMMEDIATE")
        count_row = await (await db.execute(
            f"SELECT COUNT(*) FROM personal_goal_events WHERE user_id=? AND day_key=? AND event_key IN ({placeholders})",
            (user_id, day, *keys),
        )).fetchone()
        if int((count_row[0] if count_row else 0) or 0) < GOAL_COUNT:
            await db.rollback()
            return False
        cur = await db.execute(
            "UPDATE personal_goal_days SET reward_claimed=1, updated_at=CURRENT_TIMESTAMP WHERE user_id=? AND day_key=? AND reward_claimed=0",
            (user_id, day),
        )
        if cur.rowcount != 1:
            await db.rollback()
            return False
        try:
            await apply_reward_bundle(
                db,
                user_id,
                stars=GOAL_REWARD_STARS,
                xp_source=f"personal_goal:{user_id}:{day}",
                xp_amount=GOAL_REWARD_XP,
                weekly_increment=1,
            )
        except Exception:
            await db.rollback()
            raise
        await db.commit()
        return True


async def get_personal_goal_metrics() -> PersonalGoalMetrics:
    day = _day_key()
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        async def scalar(sql: str, params: tuple = ()) -> int:
            row = await (await db.execute(sql, params)).fetchone()
            return int((row[0] if row else 0) or 0)
        participants = await scalar("SELECT COUNT(*) FROM personal_goal_days WHERE day_key=?", (day,))
        completed = await scalar(
            "SELECT COUNT(*) FROM (SELECT user_id FROM personal_goal_events WHERE day_key=? GROUP BY user_id HAVING COUNT(*)>=?)",
            (day, GOAL_COUNT),
        )
        rewards = await scalar(
            "SELECT COUNT(*) FROM personal_goal_days WHERE day_key=? AND reward_claimed=1", (day,)
        )
    rate = int(round((completed / participants) * 100)) if participants else 0
    return PersonalGoalMetrics(participants, completed, rewards, rate)

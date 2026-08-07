from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import aiosqlite

from .repository import DB_PATH


COMEBACK_MIN_DAYS = 2
COMEBACK_REWARD_STARS = 15
COMEBACK_REWARD_XP = 40


@dataclass(frozen=True)
class ReactivationProfile:
    last_seen_day: str | None
    days_away: int
    comeback_count: int
    best_gap_days: int
    reward_available: bool
    reward_claimed_this_week: bool


@dataclass(frozen=True)
class ReactivationMetrics:
    returns_7d: int
    unique_returners_7d: int
    rewards_7d: int
    avg_gap_days: int
    max_gap_days: int


def _week_key(today: date | None = None) -> str:
    current = today or date.today()
    iso = current.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


async def _ensure_schema(db: aiosqlite.Connection) -> None:
    await db.executescript(
        """
        CREATE TABLE IF NOT EXISTS reactivation_state (
            user_id INTEGER PRIMARY KEY,
            last_seen_day TEXT NOT NULL,
            comeback_count INTEGER NOT NULL DEFAULT 0,
            best_gap_days INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS reactivation_events (
            user_id INTEGER NOT NULL,
            return_day TEXT NOT NULL,
            previous_day TEXT NOT NULL,
            gap_days INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id, return_day)
        );
        CREATE TABLE IF NOT EXISTS reactivation_rewards (
            user_id INTEGER NOT NULL,
            week_key TEXT NOT NULL,
            claimed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id, week_key)
        );
        """
    )


async def record_reactivation_visit(user_id: int, *, today: date | None = None) -> ReactivationProfile:
    if user_id <= 0:
        return ReactivationProfile(None, 0, 0, 0, False, False)
    current = today or date.today()
    current_key = current.isoformat()
    week = _week_key(current)
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        await db.execute("BEGIN IMMEDIATE")
        row = await (await db.execute(
            "SELECT last_seen_day, comeback_count, best_gap_days FROM reactivation_state WHERE user_id=?",
            (user_id,),
        )).fetchone()
        days_away = 0
        comeback_count = int(row[1]) if row else 0
        best_gap = int(row[2]) if row else 0
        previous_day = str(row[0]) if row else None
        if previous_day:
            previous = date.fromisoformat(previous_day)
            days_away = max(0, (current - previous).days)
            if days_away >= COMEBACK_MIN_DAYS:
                inserted = await db.execute(
                    "INSERT OR IGNORE INTO reactivation_events(user_id, return_day, previous_day, gap_days) VALUES (?, ?, ?, ?)",
                    (user_id, current_key, previous_day, days_away),
                )
                if inserted.rowcount == 1:
                    comeback_count += 1
                    best_gap = max(best_gap, days_away)
        await db.execute(
            "INSERT INTO reactivation_state(user_id, last_seen_day, comeback_count, best_gap_days) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET last_seen_day=excluded.last_seen_day, comeback_count=excluded.comeback_count, "
            "best_gap_days=excluded.best_gap_days, updated_at=CURRENT_TIMESTAMP",
            (user_id, current_key, comeback_count, best_gap),
        )
        event_row = await (await db.execute(
            "SELECT gap_days, previous_day FROM reactivation_events WHERE user_id=? AND return_day=?",
            (user_id, current_key),
        )).fetchone()
        reward_row = await (await db.execute(
            "SELECT 1 FROM reactivation_rewards WHERE user_id=? AND week_key=?",
            (user_id, week),
        )).fetchone()
        await db.commit()
    reward_claimed = bool(reward_row)
    event_gap = int(event_row[0]) if event_row else 0
    event_previous = str(event_row[1]) if event_row else previous_day
    return ReactivationProfile(event_previous, event_gap, comeback_count, best_gap, bool(event_row) and not reward_claimed, reward_claimed)


async def get_reactivation_profile(user_id: int, *, today: date | None = None) -> ReactivationProfile:
    if user_id <= 0:
        return ReactivationProfile(None, 0, 0, 0, False, False)
    current = today or date.today()
    current_key = current.isoformat()
    week = _week_key(current)
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        row = await (await db.execute(
            "SELECT last_seen_day, comeback_count, best_gap_days FROM reactivation_state WHERE user_id=?",
            (user_id,),
        )).fetchone()
        event_row = await (await db.execute(
            "SELECT gap_days, previous_day FROM reactivation_events WHERE user_id=? AND return_day=?",
            (user_id, current_key),
        )).fetchone()
        reward_row = await (await db.execute(
            "SELECT 1 FROM reactivation_rewards WHERE user_id=? AND week_key=?",
            (user_id, week),
        )).fetchone()
    if not row:
        return ReactivationProfile(None, 0, 0, 0, False, bool(reward_row))
    last_seen = str(event_row[1]) if event_row else str(row[0])
    gap = int(event_row[0]) if event_row else 0
    return ReactivationProfile(last_seen, gap, int(row[1]), int(row[2]), bool(event_row) and not reward_row, bool(reward_row))


async def claim_reactivation_reward(user_id: int, *, today: date | None = None) -> bool:
    current = today or date.today()
    current_key = current.isoformat()
    week = _week_key(current)
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        await db.execute("BEGIN IMMEDIATE")
        event = await (await db.execute(
            "SELECT gap_days FROM reactivation_events WHERE user_id=? AND return_day=? AND gap_days>=?",
            (user_id, current_key, COMEBACK_MIN_DAYS),
        )).fetchone()
        if not event:
            await db.rollback()
            return False
        cur = await db.execute(
            "INSERT OR IGNORE INTO reactivation_rewards(user_id, week_key) VALUES (?, ?)",
            (user_id, week),
        )
        await db.commit()
        return cur.rowcount == 1


async def get_reactivation_metrics() -> ReactivationMetrics:
    since = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        row = await (await db.execute(
            "SELECT COUNT(*), COUNT(DISTINCT user_id), COALESCE(AVG(gap_days),0), COALESCE(MAX(gap_days),0) "
            "FROM reactivation_events WHERE created_at>=?",
            (since,),
        )).fetchone()
        rewards = await (await db.execute(
            "SELECT COUNT(*) FROM reactivation_rewards WHERE claimed_at>=?",
            (since,),
        )).fetchone()
    return ReactivationMetrics(
        int(row[0] or 0),
        int(row[1] or 0),
        int((rewards[0] if rewards else 0) or 0),
        int(round(float(row[2] or 0))),
        int(row[3] or 0),
    )

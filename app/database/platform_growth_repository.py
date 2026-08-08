from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import aiosqlite

from .platform_progress_repository import apply_reward_bundle, ensure_reward_schema
from .repository import DB_PATH


@dataclass(frozen=True)
class DailyActivity:
    streak: int
    best_streak: int
    last_claim_date: str | None
    claimed_today: bool
    next_reward: int


@dataclass(frozen=True)
class GrowthMetrics:
    dau: int
    wau: int
    mau: int
    daily_claims: int
    active_streaks: int
    product_events_24h: int


async def _ensure_schema(db: aiosqlite.Connection) -> None:
    await db.executescript(
        """
        CREATE TABLE IF NOT EXISTS daily_activity (
            user_id INTEGER PRIMARY KEY,
            streak INTEGER NOT NULL DEFAULT 0,
            best_streak INTEGER NOT NULL DEFAULT 0,
            last_claim_date TEXT,
            total_claims INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS product_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            event_name TEXT NOT NULL,
            event_day TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_product_events_name_time
            ON product_events(event_name, created_at);
        CREATE INDEX IF NOT EXISTS idx_product_events_user_day
            ON product_events(user_id, event_day);
        CREATE TABLE IF NOT EXISTS action_cooldowns (
            user_id INTEGER NOT NULL,
            action_key TEXT NOT NULL,
            available_at TEXT NOT NULL,
            PRIMARY KEY(user_id, action_key)
        );
        """
    )


def _reward_for_streak(streak: int) -> int:
    return min(25, 2 + max(0, streak - 1) * 2)


async def record_product_event(user_id: int, event_name: str) -> None:
    event_name = event_name.strip()[:64]
    if not event_name:
        return
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        await db.execute(
            "INSERT INTO product_events(user_id, event_name, event_day) VALUES (?, ?, ?)",
            (user_id, event_name, today),
        )
        await db.commit()


async def get_daily_activity(user_id: int) -> DailyActivity:
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        row = await (await db.execute(
            "SELECT streak, best_streak, last_claim_date FROM daily_activity WHERE user_id = ?",
            (user_id,),
        )).fetchone()
    streak, best, last = (int(row[0]), int(row[1]), row[2]) if row else (0, 0, None)
    return DailyActivity(streak, best, last, last == today, _reward_for_streak(streak + 1))


async def claim_daily_activity(user_id: int) -> tuple[bool, DailyActivity, int]:
    today = date.today()
    yesterday = (today - timedelta(days=1)).isoformat()
    today_s = today.isoformat()
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        await ensure_reward_schema(db)
        await db.execute("BEGIN IMMEDIATE")
        row = await (await db.execute(
            "SELECT streak, best_streak, last_claim_date FROM daily_activity WHERE user_id = ?",
            (user_id,),
        )).fetchone()
        if row and row[2] == today_s:
            await db.rollback()
            activity = DailyActivity(int(row[0]), int(row[1]), row[2], True, _reward_for_streak(int(row[0]) + 1))
            return False, activity, 0
        previous_streak = int(row[0]) if row else 0
        streak = previous_streak + 1 if row and row[2] == yesterday else 1
        best = max(int(row[1]) if row else 0, streak)
        reward = _reward_for_streak(streak)
        try:
            await db.execute(
                """INSERT INTO daily_activity(user_id, streak, best_streak, last_claim_date, total_claims, updated_at)
                   VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                   ON CONFLICT(user_id) DO UPDATE SET
                       streak=excluded.streak,
                       best_streak=excluded.best_streak,
                       last_claim_date=excluded.last_claim_date,
                       total_claims=daily_activity.total_claims+1,
                       updated_at=CURRENT_TIMESTAMP""",
                (user_id, streak, best, today_s),
            )
            await apply_reward_bundle(db, user_id, stars=reward)
            await db.execute(
                "INSERT INTO product_events(user_id, event_name, event_day) VALUES (?, 'daily_claim', ?)",
                (user_id, today_s),
            )
        except Exception:
            await db.rollback()
            raise
        await db.commit()
    return True, DailyActivity(streak, best, today_s, True, _reward_for_streak(streak + 1)), reward


async def acquire_action_slot(user_id: int, action_key: str, cooldown_seconds: int) -> bool:
    now = datetime.now(timezone.utc)
    available = now + timedelta(seconds=max(1, cooldown_seconds))
    now_s = now.strftime("%Y-%m-%d %H:%M:%S")
    available_s = available.strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        await db.execute("BEGIN IMMEDIATE")
        row = await (await db.execute(
            "SELECT available_at FROM action_cooldowns WHERE user_id=? AND action_key=?",
            (user_id, action_key[:64]),
        )).fetchone()
        if row and row[0] > now_s:
            await db.rollback()
            return False
        await db.execute(
            """INSERT INTO action_cooldowns(user_id, action_key, available_at) VALUES (?, ?, ?)
               ON CONFLICT(user_id, action_key) DO UPDATE SET available_at=excluded.available_at""",
            (user_id, action_key[:64], available_s),
        )
        await db.commit()
        return True


async def get_growth_metrics() -> GrowthMetrics:
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        async def scalar(sql: str, params: tuple = ()) -> int:
            row = await (await db.execute(sql, params)).fetchone()
            return int((row[0] if row else 0) or 0)
        dau = await scalar("SELECT COUNT(DISTINCT user_id) FROM product_events WHERE created_at >= datetime('now','-1 day')")
        wau = await scalar("SELECT COUNT(DISTINCT user_id) FROM product_events WHERE created_at >= datetime('now','-7 day')")
        mau = await scalar("SELECT COUNT(DISTINCT user_id) FROM product_events WHERE created_at >= datetime('now','-30 day')")
        claims = await scalar("SELECT COUNT(*) FROM product_events WHERE event_name='daily_claim' AND created_at >= datetime('now','-1 day')")
        streaks = await scalar("SELECT COUNT(*) FROM daily_activity WHERE streak >= 2")
        events = await scalar("SELECT COUNT(*) FROM product_events WHERE created_at >= datetime('now','-1 day')")
    return GrowthMetrics(dau, wau, mau, claims, streaks, events)

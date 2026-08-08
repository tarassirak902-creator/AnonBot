from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import aiosqlite

from .repository import DB_PATH


WEEKLY_TARGET = 7
WEEKLY_REWARD = 20


@dataclass(frozen=True)
class ProgressProfile:
    xp: int
    level: int
    level_name: str
    current_level_xp: int
    next_level_xp: int
    weekly_progress: int
    weekly_target: int
    weekly_reward_claimed: bool


@dataclass(frozen=True)
class ProgressMetrics:
    tracked_users: int
    level_5_plus: int
    weekly_completed: int
    weekly_rewards_claimed: int
    xp_issued_7d: int


def _week_key(today: date | None = None) -> str:
    current = today or date.today()
    monday = current - timedelta(days=current.weekday())
    return monday.isoformat()


def _level_for_xp(xp: int) -> tuple[int, str, int, int]:
    thresholds = [
        (1, "Новичок", 0),
        (2, "Знакомый", 50),
        (3, "Активный", 150),
        (4, "Надёжный", 300),
        (5, "Лидер", 550),
        (6, "Легенда", 900),
    ]
    level, name, floor = thresholds[0]
    next_floor = thresholds[1][2]
    for index, item in enumerate(thresholds):
        if xp < item[2]:
            break
        level, name, floor = item
        next_floor = thresholds[index + 1][2] if index + 1 < len(thresholds) else floor + 500
    return level, name, xp - floor, max(1, next_floor - floor)


async def _ensure_schema(db: aiosqlite.Connection) -> None:
    await db.executescript(
        """
        CREATE TABLE IF NOT EXISTS account_progress (
            user_id INTEGER PRIMARY KEY,
            xp INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS weekly_progress (
            user_id INTEGER NOT NULL,
            week_key TEXT NOT NULL,
            progress INTEGER NOT NULL DEFAULT 0,
            reward_claimed INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id, week_key)
        );
        CREATE TABLE IF NOT EXISTS xp_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            source_key TEXT NOT NULL,
            amount INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, source_key)
        );
        """
    )


async def ensure_reward_schema(db: aiosqlite.Connection) -> None:
    """Prepare reward tables before a transactional claim begins."""
    await _ensure_schema(db)


async def apply_reward_bundle(
    db: aiosqlite.Connection,
    user_id: int,
    *,
    stars: int = 0,
    xp_source: str | None = None,
    xp_amount: int = 0,
    weekly_increment: int = 0,
) -> None:
    """Apply stars and XP inside the caller's existing transaction.

    Schema creation must happen before BEGIN via ensure_reward_schema(). This
    function deliberately performs no DDL, so rollback remains reliable.
    """
    stars = max(0, min(int(stars), 100_000))
    xp_amount = max(0, min(int(xp_amount), 500))
    weekly_increment = max(0, min(int(weekly_increment), WEEKLY_TARGET))

    if stars:
        cur = await db.execute(
            "UPDATE users SET stars_balance=COALESCE(stars_balance,0)+? WHERE user_id=?",
            (stars, user_id),
        )
        if cur.rowcount != 1:
            raise RuntimeError("reward user row not found")

    if xp_amount and xp_source:
        source_key = xp_source.strip()[:96]
        if not source_key:
            raise ValueError("xp_source is required for XP reward")
        cur = await db.execute(
            "INSERT OR IGNORE INTO xp_ledger(user_id, source_key, amount) VALUES (?, ?, ?)",
            (user_id, source_key, xp_amount),
        )
        if cur.rowcount == 1:
            await db.execute(
                """INSERT INTO account_progress(user_id, xp) VALUES (?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                       xp=account_progress.xp+excluded.xp,
                       updated_at=CURRENT_TIMESTAMP""",
                (user_id, xp_amount),
            )
            if weekly_increment:
                week = _week_key()
                await db.execute(
                    """INSERT INTO weekly_progress(user_id, week_key, progress) VALUES (?, ?, ?)
                       ON CONFLICT(user_id, week_key) DO UPDATE SET
                           progress=MIN(?, weekly_progress.progress+excluded.progress),
                           updated_at=CURRENT_TIMESTAMP""",
                    (user_id, week, weekly_increment, WEEKLY_TARGET),
                )


async def grant_xp_once(user_id: int, source_key: str, amount: int, weekly_increment: int = 0) -> bool:
    source_key = source_key.strip()[:96]
    amount = max(0, min(int(amount), 500))
    weekly_increment = max(0, min(int(weekly_increment), WEEKLY_TARGET))
    if user_id <= 0 or not source_key or amount <= 0:
        return False
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        await db.execute("BEGIN IMMEDIATE")
        cur = await db.execute(
            "INSERT OR IGNORE INTO xp_ledger(user_id, source_key, amount) VALUES (?, ?, ?)",
            (user_id, source_key, amount),
        )
        if cur.rowcount != 1:
            await db.rollback()
            return False
        await db.execute(
            """INSERT INTO account_progress(user_id, xp) VALUES (?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                   xp=account_progress.xp+excluded.xp,
                   updated_at=CURRENT_TIMESTAMP""",
            (user_id, amount),
        )
        if weekly_increment:
            week = _week_key()
            await db.execute(
                """INSERT INTO weekly_progress(user_id, week_key, progress) VALUES (?, ?, ?)
                   ON CONFLICT(user_id, week_key) DO UPDATE SET
                       progress=MIN(?, weekly_progress.progress+excluded.progress),
                       updated_at=CURRENT_TIMESTAMP""",
                (user_id, week, weekly_increment, WEEKLY_TARGET),
            )
        await db.commit()
        return True


async def get_progress_profile(user_id: int) -> ProgressProfile:
    week = _week_key()
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        xp_row = await (await db.execute(
            "SELECT xp FROM account_progress WHERE user_id=?", (user_id,)
        )).fetchone()
        week_row = await (await db.execute(
            "SELECT progress, reward_claimed FROM weekly_progress WHERE user_id=? AND week_key=?",
            (user_id, week),
        )).fetchone()
    xp = int((xp_row[0] if xp_row else 0) or 0)
    progress = int((week_row[0] if week_row else 0) or 0)
    claimed = bool(week_row[1]) if week_row else False
    level, name, current, required = _level_for_xp(xp)
    return ProgressProfile(xp, level, name, current, required, progress, WEEKLY_TARGET, claimed)


async def claim_weekly_reward(user_id: int) -> bool:
    week = _week_key()
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await ensure_reward_schema(db)
        await db.execute("BEGIN IMMEDIATE")
        cur = await db.execute(
            """UPDATE weekly_progress SET reward_claimed=1, updated_at=CURRENT_TIMESTAMP
               WHERE user_id=? AND week_key=? AND progress>=? AND reward_claimed=0""",
            (user_id, week, WEEKLY_TARGET),
        )
        if cur.rowcount != 1:
            await db.rollback()
            return False
        try:
            await apply_reward_bundle(db, user_id, stars=WEEKLY_REWARD)
        except Exception:
            await db.rollback()
            raise
        await db.commit()
        return True


async def get_progress_metrics() -> ProgressMetrics:
    week = _week_key()
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        async def scalar(sql: str, params: tuple = ()) -> int:
            row = await (await db.execute(sql, params)).fetchone()
            return int((row[0] if row else 0) or 0)
        tracked = await scalar("SELECT COUNT(*) FROM account_progress")
        level_5 = await scalar("SELECT COUNT(*) FROM account_progress WHERE xp >= 550")
        completed = await scalar(
            "SELECT COUNT(*) FROM weekly_progress WHERE week_key=? AND progress>=?",
            (week, WEEKLY_TARGET),
        )
        claimed = await scalar(
            "SELECT COUNT(*) FROM weekly_progress WHERE week_key=? AND reward_claimed=1", (week,)
        )
        issued = await scalar(
            "SELECT COALESCE(SUM(amount),0) FROM xp_ledger WHERE created_at >= datetime('now','-7 day')"
        )
    return ProgressMetrics(tracked, level_5, completed, claimed, issued)

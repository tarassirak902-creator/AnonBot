from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

import aiosqlite

from .repository import DB_PATH

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FunnelMetrics:
    starts: int
    searchers: int
    matched: int
    completed: int
    repeat_searchers: int
    d1_eligible: int
    d1_returned: int
    d7_eligible: int
    d7_returned: int


async def _ensure_schema(db: aiosqlite.Connection) -> None:
    await db.executescript(
        """
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
        """
    )


async def record_product_event_safe(user_id: int, event_name: str) -> bool:
    """Record analytics without ever breaking the user-facing action."""
    event_name = (event_name or "").strip()[:64]
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return False
    if user_id <= 0 or not event_name:
        return False
    try:
        async with aiosqlite.connect(DB_PATH, timeout=10) as db:
            await _ensure_schema(db)
            await db.execute(
                "INSERT INTO product_events(user_id,event_name,event_day) VALUES(?,?,?)",
                (user_id, event_name, date.today().isoformat()),
            )
            await db.commit()
        return True
    except Exception:
        logger.exception("Не удалось записать product event: user=%s event=%s", user_id, event_name)
        return False


async def get_funnel_metrics(days: int = 7) -> FunnelMetrics:
    days = max(1, min(int(days), 90))
    window = f"-{days} day"
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)

        async def scalar(sql: str, params: tuple = ()) -> int:
            row = await (await db.execute(sql, params)).fetchone()
            return int((row[0] if row else 0) or 0)

        async def unique(event: str) -> int:
            return await scalar(
                "SELECT COUNT(DISTINCT user_id) FROM product_events WHERE event_name=? AND created_at>=datetime('now',?)",
                (event, window),
            )

        starts = await unique("app_start")
        searchers = await unique("search_started")
        matched = await unique("match_found")
        completed = await unique("dialog_completed")
        repeat_searchers = await scalar(
            """SELECT COUNT(*) FROM (
                   SELECT user_id FROM product_events
                    WHERE event_name='search_started' AND created_at>=datetime('now',?)
                    GROUP BY user_id HAVING COUNT(*)>=2
               )""",
            (window,),
        )

        # Retention cohorts start only once instrumentation has an app_start event.
        d1_eligible = await scalar(
            """WITH cohorts AS (
                   SELECT user_id, MIN(event_day) first_day
                     FROM product_events WHERE event_name='app_start' GROUP BY user_id
               )
               SELECT COUNT(*) FROM cohorts WHERE date(first_day)<=date('now','-1 day')"""
        )
        d1_returned = await scalar(
            """WITH cohorts AS (
                   SELECT user_id, MIN(event_day) first_day
                     FROM product_events WHERE event_name='app_start' GROUP BY user_id
               )
               SELECT COUNT(*) FROM cohorts c
                WHERE date(c.first_day)<=date('now','-1 day')
                  AND EXISTS (
                      SELECT 1 FROM product_events e
                       WHERE e.user_id=c.user_id AND date(e.event_day)=date(c.first_day,'+1 day')
                  )"""
        )
        d7_eligible = await scalar(
            """WITH cohorts AS (
                   SELECT user_id, MIN(event_day) first_day
                     FROM product_events WHERE event_name='app_start' GROUP BY user_id
               )
               SELECT COUNT(*) FROM cohorts WHERE date(first_day)<=date('now','-7 day')"""
        )
        d7_returned = await scalar(
            """WITH cohorts AS (
                   SELECT user_id, MIN(event_day) first_day
                     FROM product_events WHERE event_name='app_start' GROUP BY user_id
               )
               SELECT COUNT(*) FROM cohorts c
                WHERE date(c.first_day)<=date('now','-7 day')
                  AND EXISTS (
                      SELECT 1 FROM product_events e
                       WHERE e.user_id=c.user_id AND date(e.event_day)=date(c.first_day,'+7 day')
                  )"""
        )

    return FunnelMetrics(
        starts=starts,
        searchers=searchers,
        matched=matched,
        completed=completed,
        repeat_searchers=repeat_searchers,
        d1_eligible=d1_eligible,
        d1_returned=d1_returned,
        d7_eligible=d7_eligible,
        d7_returned=d7_returned,
    )

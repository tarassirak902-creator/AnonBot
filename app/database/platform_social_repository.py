from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import aiosqlite

from .repository import DB_PATH


@dataclass(frozen=True)
class ReputationSummary:
    positive: int
    neutral: int
    negative: int

    @property
    def total(self) -> int:
        return self.positive + self.neutral + self.negative

    @property
    def positive_percent(self) -> int:
        return round(self.positive * 100 / self.total) if self.total else 0


async def _ensure_schema(db: aiosqlite.Connection) -> None:
    await db.executescript(
        """
        CREATE TABLE IF NOT EXISTS dialog_ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rater_id INTEGER NOT NULL,
            rated_user_id INTEGER NOT NULL,
            dialog_key TEXT NOT NULL,
            rating INTEGER NOT NULL CHECK (rating IN (-1, 0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(rater_id, dialog_key)
        );
        CREATE INDEX IF NOT EXISTS idx_dialog_ratings_user
            ON dialog_ratings(rated_user_id, created_at);

        CREATE TABLE IF NOT EXISTS user_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            kind TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_user_notifications_feed
            ON user_notifications(user_id, is_read, created_at DESC);
        """
    )


async def rate_dialog(rater_id: int, rated_user_id: int, dialog_key: str, rating: int) -> bool:
    if rating not in {-1, 0, 1} or rater_id == rated_user_id or not dialog_key:
        return False
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        cursor = await db.execute(
            "INSERT OR IGNORE INTO dialog_ratings (rater_id, rated_user_id, dialog_key, rating) VALUES (?, ?, ?, ?)",
            (rater_id, rated_user_id, dialog_key, rating),
        )
        await db.commit()
        return cursor.rowcount == 1


async def get_reputation_summary(user_id: int) -> ReputationSummary:
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        row = await (await db.execute(
            """SELECT
                   SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END),
                   SUM(CASE WHEN rating = 0 THEN 1 ELSE 0 END),
                   SUM(CASE WHEN rating = -1 THEN 1 ELSE 0 END)
               FROM dialog_ratings WHERE rated_user_id = ?""",
            (user_id,),
        )).fetchone()
    return ReputationSummary(*(int(value or 0) for value in row))


async def add_notification(user_id: int, kind: str, title: str, body: str) -> None:
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        await db.execute(
            "INSERT INTO user_notifications (user_id, kind, title, body) VALUES (?, ?, ?, ?)",
            (user_id, kind[:32], title[:120], body[:800]),
        )
        await db.commit()


async def get_notifications(user_id: int, limit: int = 10) -> list[tuple]:
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        return await (await db.execute(
            """SELECT id, kind, title, body, is_read, created_at
               FROM user_notifications WHERE user_id = ?
               ORDER BY is_read ASC, id DESC LIMIT ?""",
            (user_id, max(1, min(limit, 30))),
        )).fetchall()


async def mark_notifications_read(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        cursor = await db.execute(
            "UPDATE user_notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0",
            (user_id,),
        )
        await db.commit()
        return cursor.rowcount


async def unread_notification_count(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        row = await (await db.execute(
            "SELECT COUNT(*) FROM user_notifications WHERE user_id = ? AND is_read = 0",
            (user_id,),
        )).fetchone()
        return int(row[0] or 0)

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import aiosqlite

from .repository import DB_PATH


@dataclass(frozen=True)
class PendingRating:
    token: str
    rater_id: int
    rated_user_id: int
    dialog_key: str
    expires_at: str


async def _ensure_schema(db: aiosqlite.Connection) -> None:
    await db.executescript(
        """
        CREATE TABLE IF NOT EXISTS pending_dialog_ratings (
            token TEXT PRIMARY KEY,
            rater_id INTEGER NOT NULL,
            rated_user_id INTEGER NOT NULL,
            dialog_key TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            consumed_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(rater_id, dialog_key)
        );
        CREATE INDEX IF NOT EXISTS idx_pending_dialog_ratings_user
            ON pending_dialog_ratings(rater_id, expires_at);
        """
    )


def build_dialog_key(user_a: int, user_b: int, ended_at: datetime | None = None) -> str:
    ended_at = ended_at or datetime.now(timezone.utc)
    low, high = sorted((int(user_a), int(user_b)))
    bucket = int(ended_at.timestamp())
    return f"{low}:{high}:{bucket}"


async def create_rating_pair(
    user_a: int,
    user_b: int,
    *,
    dialog_key: str | None = None,
    ttl_minutes: int = 60,
) -> tuple[PendingRating, PendingRating]:
    if user_a == user_b:
        raise ValueError("Нельзя создать оценку диалога с самим собой")
    ttl_minutes = max(5, min(int(ttl_minutes), 24 * 60))
    dialog_key = dialog_key or build_dialog_key(user_a, user_b)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
    expires_text = expires_at.strftime("%Y-%m-%d %H:%M:%S")

    first = PendingRating(secrets.token_urlsafe(9), user_a, user_b, dialog_key, expires_text)
    second = PendingRating(secrets.token_urlsafe(9), user_b, user_a, dialog_key, expires_text)

    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        await db.execute("BEGIN IMMEDIATE")
        for item in (first, second):
            await db.execute(
                """INSERT OR REPLACE INTO pending_dialog_ratings
                   (token, rater_id, rated_user_id, dialog_key, expires_at, consumed_at)
                   VALUES (?, ?, ?, ?, ?, NULL)""",
                (item.token, item.rater_id, item.rated_user_id, item.dialog_key, item.expires_at),
            )
        await db.commit()
    return first, second


async def consume_rating_token(token: str, rater_id: int) -> PendingRating | None:
    now_text = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        await db.execute("BEGIN IMMEDIATE")
        row = await (await db.execute(
            """SELECT token, rater_id, rated_user_id, dialog_key, expires_at
               FROM pending_dialog_ratings
               WHERE token = ? AND rater_id = ? AND consumed_at IS NULL AND expires_at >= ?""",
            (token, rater_id, now_text),
        )).fetchone()
        if not row:
            await db.rollback()
            return None
        cursor = await db.execute(
            "UPDATE pending_dialog_ratings SET consumed_at = CURRENT_TIMESTAMP WHERE token = ? AND consumed_at IS NULL",
            (token,),
        )
        if cursor.rowcount != 1:
            await db.rollback()
            return None
        await db.commit()
    return PendingRating(str(row[0]), int(row[1]), int(row[2]), str(row[3]), str(row[4]))


async def cleanup_expired_rating_tokens() -> int:
    now_text = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH, timeout=10) as db:
        await _ensure_schema(db)
        cursor = await db.execute(
            "DELETE FROM pending_dialog_ratings WHERE expires_at < ? OR consumed_at IS NOT NULL",
            (now_text,),
        )
        await db.commit()
        return cursor.rowcount

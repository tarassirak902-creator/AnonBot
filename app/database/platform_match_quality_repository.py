from __future__ import annotations

from dataclasses import dataclass

import aiosqlite

from .repository import DB_PATH


@dataclass(frozen=True)
class MatchQualityProfile:
    user_id: int
    ratings: int
    positive: int
    neutral: int
    negative: int
    score: int


@dataclass(frozen=True)
class MatchQualityMetrics:
    rated_users: int
    ratings: int
    positive: int
    neutral: int
    negative: int
    low_quality_users: int


async def ensure_match_quality_schema(conn: aiosqlite.Connection) -> None:
    await conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS match_quality (
            user_id INTEGER PRIMARY KEY,
            ratings INTEGER NOT NULL DEFAULT 0,
            positive INTEGER NOT NULL DEFAULT 0,
            neutral INTEGER NOT NULL DEFAULT 0,
            negative INTEGER NOT NULL DEFAULT 0,
            score INTEGER NOT NULL DEFAULT 50,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS match_quality_events (
            dialog_key TEXT NOT NULL,
            rater_id INTEGER NOT NULL,
            rated_user_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(dialog_key, rater_id)
        );
        """
    )


def _score(positive: int, neutral: int, negative: int) -> int:
    total = positive + neutral + negative
    if total <= 0:
        return 50
    weighted = positive * 100 + neutral * 55 + negative * 10
    # Bayesian-style prior keeps new users close to neutral instead of creating
    # extreme quality tiers from a single rating.
    return max(0, min(100, int(round((weighted + 300) / (total + 6)))))


async def record_match_quality_rating(
    rater_id: int,
    rated_user_id: int,
    dialog_key: str,
    rating: int,
) -> bool:
    if rater_id <= 0 or rated_user_id <= 0 or rater_id == rated_user_id:
        return False
    if rating not in {-1, 0, 1} or not dialog_key:
        return False

    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await ensure_match_quality_schema(conn)
        await conn.execute("BEGIN IMMEDIATE")
        cur = await conn.execute(
            "INSERT OR IGNORE INTO match_quality_events(dialog_key,rater_id,rated_user_id,rating) VALUES (?,?,?,?)",
            (dialog_key, rater_id, rated_user_id, rating),
        )
        if cur.rowcount != 1:
            await conn.rollback()
            return False

        await conn.execute(
            "INSERT OR IGNORE INTO match_quality(user_id) VALUES (?)",
            (rated_user_id,),
        )
        column = "positive" if rating == 1 else "neutral" if rating == 0 else "negative"
        await conn.execute(
            f"UPDATE match_quality SET ratings=ratings+1, {column}={column}+1, updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
            (rated_user_id,),
        )
        row = await (
            await conn.execute(
                "SELECT positive,neutral,negative FROM match_quality WHERE user_id=?",
                (rated_user_id,),
            )
        ).fetchone()
        score = _score(int(row[0]), int(row[1]), int(row[2])) if row else 50
        await conn.execute(
            "UPDATE match_quality SET score=? WHERE user_id=?",
            (score, rated_user_id),
        )
        await conn.commit()
        return True


async def get_match_quality_profile(user_id: int) -> MatchQualityProfile:
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await ensure_match_quality_schema(conn)
        row = await (
            await conn.execute(
                "SELECT ratings,positive,neutral,negative,score FROM match_quality WHERE user_id=?",
                (user_id,),
            )
        ).fetchone()
    if not row:
        return MatchQualityProfile(user_id, 0, 0, 0, 0, 50)
    return MatchQualityProfile(user_id, *(int(value or 0) for value in row))


async def get_match_quality_metrics() -> MatchQualityMetrics:
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await ensure_match_quality_schema(conn)
        row = await (
            await conn.execute(
                "SELECT COUNT(*),COALESCE(SUM(ratings),0),COALESCE(SUM(positive),0),COALESCE(SUM(neutral),0),COALESCE(SUM(negative),0),"
                "SUM(CASE WHEN ratings>=3 AND score<35 THEN 1 ELSE 0 END) FROM match_quality"
            )
        ).fetchone()
    values = [int(value or 0) for value in (row or (0, 0, 0, 0, 0, 0))]
    return MatchQualityMetrics(*values)

from __future__ import annotations

from datetime import date, datetime, timedelta

import aiosqlite

from .repository import DB_PATH


async def record_recent_partners(user_id: int, partner_id: int) -> None:
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.executemany(
            "INSERT INTO recent_partners(user_id,partner_id,last_chat_at) VALUES (?,?,?) "
            "ON CONFLICT(user_id,partner_id) DO UPDATE SET last_chat_at=excluded.last_chat_at",
            [(user_id, partner_id, now), (partner_id, user_id, now)],
        )
        await conn.commit()


async def rate_user(rater_id: int, rated_user_id: int, score: int) -> None:
    if score not in (-1, 0, 1):
        raise ValueError("score must be -1, 0 or 1")
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("BEGIN IMMEDIATE")
        await conn.execute(
            "INSERT INTO chat_ratings(rater_id,rated_user_id,score) VALUES (?,?,?)",
            (rater_id, rated_user_id, score),
        )
        await conn.execute(
            "INSERT INTO user_progress(user_id) VALUES (?) ON CONFLICT(user_id) DO NOTHING",
            (rated_user_id,),
        )
        column = {1: "positive_ratings", 0: "neutral_ratings", -1: "negative_ratings"}[score]
        await conn.execute(
            f"UPDATE user_progress SET {column}={column}+1 WHERE user_id=?",
            (rated_user_id,),
        )
        await conn.commit()


async def get_reputation(user_id: int) -> dict[str, int | float]:
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        row = await (
            await conn.execute(
                "SELECT positive_ratings,neutral_ratings,negative_ratings,xp,level "
                "FROM user_progress WHERE user_id=?",
                (user_id,),
            )
        ).fetchone()
    positive, neutral, negative, xp, level = row or (0, 0, 0, 0, 1)
    total = int(positive) + int(neutral) + int(negative)
    score = round((int(positive) - int(negative)) / total * 100, 1) if total else 0.0
    return {
        "positive": int(positive),
        "neutral": int(neutral),
        "negative": int(negative),
        "total": total,
        "score": score,
        "xp": int(xp),
        "level": int(level),
    }


async def add_xp(user_id: int, amount: int) -> tuple[int, int]:
    if amount <= 0:
        return 0, 1
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("BEGIN IMMEDIATE")
        await conn.execute(
            "INSERT INTO user_progress(user_id,xp,level) VALUES (?,?,1) "
            "ON CONFLICT(user_id) DO UPDATE SET xp=xp+excluded.xp",
            (user_id, amount),
        )
        row = await (
            await conn.execute("SELECT xp FROM user_progress WHERE user_id=?", (user_id,))
        ).fetchone()
        xp = int(row[0])
        level = max(1, xp // 100 + 1)
        await conn.execute("UPDATE user_progress SET level=? WHERE user_id=?", (level, user_id))
        await conn.commit()
    return xp, level


async def claim_daily_reward(user_id: int) -> dict[str, int | bool]:
    today = date.today()
    yesterday = today - timedelta(days=1)
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("BEGIN IMMEDIATE")
        row = await (
            await conn.execute(
                "SELECT last_claim_date,streak,total_claims FROM daily_rewards WHERE user_id=?",
                (user_id,),
            )
        ).fetchone()
        last_claim = date.fromisoformat(row[0]) if row and row[0] else None
        streak = int(row[1]) if row else 0
        total_claims = int(row[2]) if row else 0
        if last_claim == today:
            await conn.rollback()
            return {"claimed": False, "streak": streak, "reward": 0, "total_claims": total_claims}
        streak = streak + 1 if last_claim == yesterday else 1
        reward = min(50, 10 + (streak - 1) * 5)
        total_claims += 1
        await conn.execute(
            "INSERT INTO daily_rewards(user_id,last_claim_date,streak,total_claims) VALUES (?,?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET last_claim_date=excluded.last_claim_date,"
            "streak=excluded.streak,total_claims=excluded.total_claims",
            (user_id, today.isoformat(), streak, total_claims),
        )
        await conn.commit()
    await add_xp(user_id, reward)
    return {"claimed": True, "streak": streak, "reward": reward, "total_claims": total_claims}

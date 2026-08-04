from __future__ import annotations

from datetime import datetime, timedelta

import aiosqlite

from app.database.repository import DB_PATH


async def _table_exists(conn: aiosqlite.Connection, table: str) -> bool:
    row = await (
        await conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
    ).fetchone()
    return row is not None


async def _columns(conn: aiosqlite.Connection, table: str) -> set[str]:
    if not await _table_exists(conn, table):
        return set()
    rows = await (await conn.execute(f"PRAGMA table_info({table})")).fetchall()
    return {str(row[1]) for row in rows}


async def ensure_engagement_schema() -> None:
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS daily_mission_claims (
                user_id INTEGER NOT NULL,
                mission_date TEXT NOT NULL,
                mission_code TEXT NOT NULL,
                reward_stars INTEGER NOT NULL DEFAULT 0,
                claimed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(user_id, mission_date, mission_code)
            );
            CREATE INDEX IF NOT EXISTS idx_daily_mission_claims_date
                ON daily_mission_claims(mission_date, claimed_at);
            """
        )
        await conn.commit()


async def load_daily_missions(user_id: int) -> list[dict[str, object]]:
    """Build three useful missions from existing counters without storing chat content."""
    await ensure_engagement_schema()
    today = datetime.now().date().isoformat()
    counters = {
        "dialog": 0,
        "message": 0,
        "question": 0,
    }
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        user_columns = await _columns(conn, "users")
        if "completed_dialogs" in user_columns or "messages_count" in user_columns:
            select_parts = []
            select_parts.append("COALESCE(completed_dialogs,0)" if "completed_dialogs" in user_columns else "0")
            select_parts.append("COALESCE(messages_count,0)" if "messages_count" in user_columns else "0")
            row = await (
                await conn.execute(
                    f"SELECT {','.join(select_parts)} FROM users WHERE user_id=?",
                    (user_id,),
                )
            ).fetchone()
            if row:
                counters["dialog"] = int(row[0] or 0)
                counters["message"] = int(row[1] or 0)

        question_columns = await _columns(conn, "anonymous_questions")
        if "sender_id" in question_columns:
            row = await (
                await conn.execute(
                    "SELECT COUNT(*) FROM anonymous_questions WHERE sender_id=? AND date(created_at)=date('now')",
                    (user_id,),
                )
            ).fetchone()
            counters["question"] = int(row[0] or 0) if row else 0

        claimed_rows = await (
            await conn.execute(
                "SELECT mission_code FROM daily_mission_claims WHERE user_id=? AND mission_date=?",
                (user_id, today),
            )
        ).fetchall()
    claimed = {str(row[0]) for row in claimed_rows}

    definitions = (
        ("dialog", "💬 Заверши диалог", min(counters["dialog"], 1), 1, 3),
        ("message", "✉️ Отправь 10 сообщений", min(counters["message"], 10), 10, 4),
        ("question", "❓ Задай вопрос", min(counters["question"], 1), 1, 3),
    )
    return [
        {
            "code": code,
            "title": title,
            "progress": progress,
            "target": target,
            "reward": reward,
            "completed": progress >= target,
            "claimed": code in claimed,
        }
        for code, title, progress, target, reward in definitions
    ]


async def claim_daily_mission(user_id: int, mission_code: str) -> dict[str, object]:
    missions = {str(item["code"]): item for item in await load_daily_missions(user_id)}
    mission = missions.get(mission_code)
    if not mission:
        return {"status": "missing", "reward": 0}
    if not mission["completed"]:
        return {"status": "incomplete", "reward": 0}
    if mission["claimed"]:
        return {"status": "claimed", "reward": 0}

    today = datetime.now().date().isoformat()
    reward = int(mission["reward"])
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("BEGIN IMMEDIATE")
        cursor = await conn.execute(
            "INSERT OR IGNORE INTO daily_mission_claims(user_id,mission_date,mission_code,reward_stars) VALUES (?,?,?,?)",
            (user_id, today, mission_code, reward),
        )
        if cursor.rowcount != 1:
            await conn.rollback()
            return {"status": "claimed", "reward": 0}
        user_columns = await _columns(conn, "users")
        if "stars_balance" in user_columns:
            await conn.execute(
                "UPDATE users SET stars_balance=COALESCE(stars_balance,0)+? WHERE user_id=?",
                (reward, user_id),
            )
        await conn.commit()
    return {"status": "ok", "reward": reward}


async def load_retention_snapshot() -> dict[str, int]:
    """Return coarse retention and engagement metrics without requiring event analytics."""
    result = {
        "users_total": 0,
        "active_24h": 0,
        "active_7d": 0,
        "returning_7d": 0,
        "dialog_users": 0,
        "mission_claims_24h": 0,
        "mission_users_7d": 0,
    }
    await ensure_engagement_schema()
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        user_columns = await _columns(conn, "users")
        if user_columns:
            row = await (await conn.execute("SELECT COUNT(*) FROM users")).fetchone()
            result["users_total"] = int(row[0] or 0) if row else 0
            if "last_activity" in user_columns:
                row = await (
                    await conn.execute(
                        "SELECT COUNT(*) FROM users WHERE last_activity>=datetime('now','-1 day')"
                    )
                ).fetchone()
                result["active_24h"] = int(row[0] or 0) if row else 0
                row = await (
                    await conn.execute(
                        "SELECT COUNT(*) FROM users WHERE last_activity>=datetime('now','-7 day')"
                    )
                ).fetchone()
                result["active_7d"] = int(row[0] or 0) if row else 0
            if {"joined_date", "last_activity"}.issubset(user_columns):
                row = await (
                    await conn.execute(
                        "SELECT COUNT(*) FROM users WHERE joined_date<datetime('now','-1 day') "
                        "AND last_activity>=datetime('now','-7 day')"
                    )
                ).fetchone()
                result["returning_7d"] = int(row[0] or 0) if row else 0
            if "completed_dialogs" in user_columns:
                row = await (
                    await conn.execute("SELECT COUNT(*) FROM users WHERE COALESCE(completed_dialogs,0)>0")
                ).fetchone()
                result["dialog_users"] = int(row[0] or 0) if row else 0

        row = await (
            await conn.execute(
                "SELECT COUNT(*) FROM daily_mission_claims WHERE claimed_at>=datetime('now','-1 day')"
            )
        ).fetchone()
        result["mission_claims_24h"] = int(row[0] or 0) if row else 0
        row = await (
            await conn.execute(
                "SELECT COUNT(DISTINCT user_id) FROM daily_mission_claims "
                "WHERE claimed_at>=datetime('now','-7 day')"
            )
        ).fetchone()
        result["mission_users_7d"] = int(row[0] or 0) if row else 0
    return result

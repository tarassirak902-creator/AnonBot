from __future__ import annotations

import json
from datetime import datetime

import aiosqlite

from .repository import DB_PATH


async def ensure_community_schema() -> None:
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id INTEGER PRIMARY KEY,
                language TEXT NOT NULL DEFAULT 'ru',
                interests_json TEXT NOT NULL DEFAULT '[]',
                allow_reconnect INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS reconnect_requests (
                requester_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(requester_id, target_id)
            );
            CREATE INDEX IF NOT EXISTS idx_reconnect_target_status
                ON reconnect_requests(target_id, status, created_at DESC);
            """
        )
        await conn.commit()


async def get_user_preferences(user_id: int) -> dict[str, object]:
    await ensure_community_schema()
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        row = await (
            await conn.execute(
                "SELECT language,interests_json,allow_reconnect FROM user_preferences WHERE user_id=?",
                (user_id,),
            )
        ).fetchone()
    if not row:
        return {"language": "ru", "interests": [], "allow_reconnect": True}
    try:
        interests = json.loads(row[1] or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        interests = []
    if not isinstance(interests, list):
        interests = []
    return {
        "language": str(row[0] or "ru"),
        "interests": [str(item) for item in interests[:10]],
        "allow_reconnect": bool(row[2]),
    }


async def set_user_preferences(
    user_id: int,
    *,
    language: str | None = None,
    interests: list[str] | None = None,
    allow_reconnect: bool | None = None,
) -> dict[str, object]:
    current = await get_user_preferences(user_id)
    normalized_language = (language or str(current["language"])).strip().lower()[:12] or "ru"
    normalized_interests = current["interests"] if interests is None else [
        item.strip()[:32] for item in interests if item and item.strip()
    ][:10]
    reconnect = bool(current["allow_reconnect"] if allow_reconnect is None else allow_reconnect)
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute(
            """INSERT INTO user_preferences(user_id,language,interests_json,allow_reconnect,updated_at)
               VALUES (?,?,?,?,?)
               ON CONFLICT(user_id) DO UPDATE SET
                 language=excluded.language,
                 interests_json=excluded.interests_json,
                 allow_reconnect=excluded.allow_reconnect,
                 updated_at=excluded.updated_at""",
            (user_id, normalized_language, json.dumps(normalized_interests, ensure_ascii=False), int(reconnect), now),
        )
        await conn.commit()
    return {
        "language": normalized_language,
        "interests": normalized_interests,
        "allow_reconnect": reconnect,
    }


async def request_reconnect(requester_id: int, target_id: int) -> str:
    if requester_id == target_id:
        raise ValueError("cannot reconnect with self")
    await ensure_community_schema()
    requester = await get_user_preferences(requester_id)
    target = await get_user_preferences(target_id)
    if not requester["allow_reconnect"] or not target["allow_reconnect"]:
        return "disabled"
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("BEGIN IMMEDIATE")
        reverse = await (
            await conn.execute(
                "SELECT status FROM reconnect_requests WHERE requester_id=? AND target_id=?",
                (target_id, requester_id),
            )
        ).fetchone()
        if reverse and reverse[0] in {"pending", "accepted"}:
            await conn.execute(
                "UPDATE reconnect_requests SET status='accepted',updated_at=? "
                "WHERE (requester_id=? AND target_id=?) OR (requester_id=? AND target_id=?)",
                (now, requester_id, target_id, target_id, requester_id),
            )
            await conn.execute(
                "INSERT OR REPLACE INTO reconnect_requests(requester_id,target_id,status,created_at,updated_at) "
                "VALUES (?,?, 'accepted', ?, ?)",
                (requester_id, target_id, now, now),
            )
            await conn.commit()
            return "matched"
        await conn.execute(
            "INSERT INTO reconnect_requests(requester_id,target_id,status,created_at,updated_at) "
            "VALUES (?,?, 'pending', ?, ?) "
            "ON CONFLICT(requester_id,target_id) DO UPDATE SET status='pending',updated_at=excluded.updated_at",
            (requester_id, target_id, now, now),
        )
        await conn.commit()
    return "pending"


async def are_reconnect_matched(user_id: int, other_id: int) -> bool:
    await ensure_community_schema()
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        row = await (
            await conn.execute(
                "SELECT 1 FROM reconnect_requests WHERE requester_id=? AND target_id=? AND status='accepted'",
                (user_id, other_id),
            )
        ).fetchone()
    return row is not None

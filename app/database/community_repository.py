from __future__ import annotations

from datetime import datetime

import aiosqlite

from .repository import DB_PATH


async def ensure_community_schema() -> None:
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS reconnect_settings (
                user_id INTEGER PRIMARY KEY,
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


async def is_reconnect_allowed(user_id: int) -> bool:
    await ensure_community_schema()
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        row = await (
            await conn.execute(
                "SELECT allow_reconnect FROM reconnect_settings WHERE user_id=?",
                (user_id,),
            )
        ).fetchone()
    return True if not row else bool(row[0])


async def set_reconnect_allowed(user_id: int, enabled: bool) -> bool:
    await ensure_community_schema()
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute(
            """INSERT INTO reconnect_settings(user_id,allow_reconnect,updated_at)
               VALUES (?,?,?)
               ON CONFLICT(user_id) DO UPDATE SET
                 allow_reconnect=excluded.allow_reconnect,
                 updated_at=excluded.updated_at""",
            (user_id, int(enabled), now),
        )
        await conn.commit()
    return bool(enabled)


async def request_reconnect(requester_id: int, target_id: int) -> str:
    if requester_id == target_id:
        raise ValueError("cannot reconnect with self")
    await ensure_community_schema()
    if not await is_reconnect_allowed(requester_id) or not await is_reconnect_allowed(target_id):
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

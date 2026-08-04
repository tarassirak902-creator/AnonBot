from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import aiosqlite

from . import repository as legacy_repository

DB_PATH = legacy_repository.DB_PATH
CURRENT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class MatchmakingSnapshot:
    queues: tuple[tuple[int, str], ...]
    active_chats: tuple[tuple[int, int, str], ...]


async def _table_columns(conn: aiosqlite.Connection, table: str) -> set[str]:
    rows = await (await conn.execute(f"PRAGMA table_info({table})")).fetchall()
    return {str(row[1]) for row in rows}


async def _table_exists(conn: aiosqlite.Connection, table: str) -> bool:
    row = await (
        await conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
    ).fetchone()
    return row is not None


async def _snapshot_matchmaking(path: str) -> MatchmakingSnapshot:
    queues: list[tuple[int, str]] = []
    active_chats: list[tuple[int, int, str]] = []
    async with aiosqlite.connect(path, timeout=10) as conn:
        if await _table_exists(conn, "queues"):
            columns = await _table_columns(conn, "queues")
            if "user_id" in columns:
                created_expr = "created_at" if "created_at" in columns else "CURRENT_TIMESTAMP"
                rows = await (
                    await conn.execute(
                        f"SELECT user_id,{created_expr} FROM queues WHERE user_id IS NOT NULL"
                    )
                ).fetchall()
                queues = [(int(row[0]), str(row[1] or datetime.now().isoformat())) for row in rows]

        if await _table_exists(conn, "active_chats"):
            columns = await _table_columns(conn, "active_chats")
            if {"user_id", "partner_id"}.issubset(columns):
                created_expr = "created_at" if "created_at" in columns else "CURRENT_TIMESTAMP"
                rows = await (
                    await conn.execute(
                        f"SELECT user_id,partner_id,{created_expr} FROM active_chats "
                        "WHERE user_id IS NOT NULL AND partner_id IS NOT NULL"
                    )
                ).fetchall()
                active_chats = [
                    (int(row[0]), int(row[1]), str(row[2] or datetime.now().isoformat()))
                    for row in rows
                ]

    return MatchmakingSnapshot(tuple(queues), tuple(active_chats))


async def _restore_matchmaking(path: str, snapshot: MatchmakingSnapshot) -> None:
    async with aiosqlite.connect(path, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")
        await conn.execute("BEGIN IMMEDIATE")
        for user_id, created_at in snapshot.queues:
            await conn.execute(
                "INSERT OR IGNORE INTO queues(user_id,created_at) VALUES (?,?)",
                (user_id, created_at),
            )
        for user_id, partner_id, created_at in snapshot.active_chats:
            await conn.execute(
                "INSERT OR REPLACE INTO active_chats(user_id,partner_id,created_at) VALUES (?,?,?)",
                (user_id, partner_id, created_at),
            )
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        await conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version,applied_at) VALUES (?,?)",
            (CURRENT_SCHEMA_VERSION, datetime.now().isoformat()),
        )
        await conn.commit()


async def init_db() -> None:
    """Initialize the database without losing legacy matchmaking state.

    The original initializer rebuilds temporary tables when their column count or
    legacy shape differs. This facade snapshots compatible rows first, invokes the
    legacy schema creation, restores the rows, and records an explicit migration
    version. New migrations should be added here rather than by column counts.
    """
    snapshot = await _snapshot_matchmaking(DB_PATH)
    await legacy_repository.init_db()
    await _restore_matchmaking(DB_PATH, snapshot)

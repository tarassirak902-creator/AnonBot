from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable

import aiosqlite

from . import repository as legacy_repository

DB_PATH = legacy_repository.DB_PATH
CURRENT_SCHEMA_VERSION = 4
Migration = Callable[[aiosqlite.Connection], Awaitable[None]]


@dataclass(frozen=True)
class MatchmakingSnapshot:
    queues: tuple[tuple[int, str], ...]
    active_chats: tuple[tuple[int, int, str], ...]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
                queues = [(int(row[0]), str(row[1] or _utc_now())) for row in rows]

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
                    (int(row[0]), int(row[1]), str(row[2] or _utc_now()))
                    for row in rows
                ]

    return MatchmakingSnapshot(tuple(queues), tuple(active_chats))


async def _create_social_schema(conn: aiosqlite.Connection) -> None:
    await conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS chat_ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rater_id INTEGER NOT NULL,
            rated_user_id INTEGER NOT NULL,
            score INTEGER NOT NULL CHECK(score IN (-1,0,1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS recent_partners (
            user_id INTEGER NOT NULL,
            partner_id INTEGER NOT NULL,
            last_chat_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id, partner_id)
        );
        CREATE TABLE IF NOT EXISTS daily_rewards (
            user_id INTEGER PRIMARY KEY,
            last_claim_date TEXT,
            streak INTEGER NOT NULL DEFAULT 0,
            total_claims INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS user_progress (
            user_id INTEGER PRIMARY KEY,
            xp INTEGER NOT NULL DEFAULT 0,
            level INTEGER NOT NULL DEFAULT 1,
            positive_ratings INTEGER NOT NULL DEFAULT 0,
            neutral_ratings INTEGER NOT NULL DEFAULT 0,
            negative_ratings INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_chat_ratings_target_time
            ON chat_ratings(rated_user_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_recent_partners_user_time
            ON recent_partners(user_id, last_chat_at DESC);
        """
    )


async def _create_reliability_indexes(conn: aiosqlite.Connection) -> None:
    definitions: dict[str, tuple[tuple[str, set[str]], ...]] = {
        "anonymous_questions": (
            (
                "CREATE INDEX IF NOT EXISTS idx_questions_sender_created "
                "ON anonymous_questions(sender_id,created_at DESC)",
                {"sender_id", "created_at"},
            ),
            (
                "CREATE INDEX IF NOT EXISTS idx_questions_receiver_status_created "
                "ON anonymous_questions(receiver_id,status,created_at DESC)",
                {"receiver_id", "status", "created_at"},
            ),
        ),
        "question_link_visits": ((
            "CREATE INDEX IF NOT EXISTS idx_question_visits_visitor "
            "ON question_link_visits(visitor_id,created_at DESC)",
            {"visitor_id", "created_at"},
        ),),
        "purchases": (
            (
                "CREATE INDEX IF NOT EXISTS idx_purchases_buyer_type_time "
                "ON purchases(buyer_id,type,timestamp DESC)",
                {"buyer_id", "type", "timestamp"},
            ),
            (
                "CREATE INDEX IF NOT EXISTS idx_purchases_receiver_type_time "
                "ON purchases(receiver_id,type,timestamp DESC)",
                {"receiver_id", "type", "timestamp"},
            ),
        ),
        "payment_ledger": ((
            "CREATE INDEX IF NOT EXISTS idx_payment_ledger_status_started "
            "ON payment_ledger(status,started_at)",
            {"status", "started_at"},
        ),),
        "premium_deliveries": ((
            "CREATE INDEX IF NOT EXISTS idx_premium_delivery_status_created "
            "ON premium_deliveries(status,created_at)",
            {"status", "created_at"},
        ),),
        "game_duels": ((
            "CREATE INDEX IF NOT EXISTS idx_game_duels_status_created "
            "ON game_duels(status,created_at)",
            {"status", "created_at"},
        ),),
    }
    for table, indexes in definitions.items():
        if not await _table_exists(conn, table):
            continue
        columns = await _table_columns(conn, table)
        for statement, required_columns in indexes:
            if required_columns.issubset(columns):
                await conn.execute(statement)


async def _migration_1_social_schema(conn: aiosqlite.Connection) -> None:
    await _create_social_schema(conn)


async def _migration_2_reliability_indexes(conn: aiosqlite.Connection) -> None:
    await _create_reliability_indexes(conn)


async def _migration_3_matchmaking_marker(conn: aiosqlite.Connection) -> None:
    # Matchmaking table normalization is performed by legacy init_db before this
    # runner. This explicit marker keeps old production databases ordered.
    return None


async def _migration_4_backup_audit(conn: aiosqlite.Connection) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS backup_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            path TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            integrity TEXT NOT NULL
        )
        """
    )


MIGRATIONS: tuple[tuple[int, Migration], ...] = (
    (1, _migration_1_social_schema),
    (2, _migration_2_reliability_indexes),
    (3, _migration_3_matchmaking_marker),
    (4, _migration_4_backup_audit),
)


async def apply_schema_migrations(conn: aiosqlite.Connection) -> list[int]:
    await conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    rows = await (await conn.execute("SELECT version FROM schema_migrations")).fetchall()
    applied = {int(row[0]) for row in rows}
    newly_applied: list[int] = []

    for version, migration in MIGRATIONS:
        if version in applied:
            continue
        await migration(conn)
        await conn.execute(
            "INSERT INTO schema_migrations(version,applied_at) VALUES (?,?)",
            (version, _utc_now()),
        )
        newly_applied.append(version)
    return newly_applied


async def get_schema_version(path: str = DB_PATH) -> int:
    async with aiosqlite.connect(path, timeout=10) as conn:
        if not await _table_exists(conn, "schema_migrations"):
            return 0
        row = await (await conn.execute("SELECT MAX(version) FROM schema_migrations")).fetchone()
        return int(row[0] or 0) if row else 0


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
        await apply_schema_migrations(conn)
        await conn.commit()


async def init_db() -> None:
    """Initialize the database without losing legacy matchmaking state."""
    snapshot = await _snapshot_matchmaking(DB_PATH)
    await legacy_repository.init_db()
    await _restore_matchmaking(DB_PATH, snapshot)

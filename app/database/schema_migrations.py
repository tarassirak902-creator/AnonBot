from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import aiosqlite

from . import repository as legacy_repository

DB_PATH = legacy_repository.DB_PATH
CURRENT_SCHEMA_VERSION = 2


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


async def _create_reliability_indexes(conn: aiosqlite.Connection) -> None:
    statements = {
        "anonymous_questions": (
            "CREATE INDEX IF NOT EXISTS idx_questions_sender_created "
            "ON anonymous_questions(sender_id,created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_questions_receiver_status_created "
            "ON anonymous_questions(receiver_id,status,created_at DESC)",
        ),
        "question_link_visits": (
            "CREATE INDEX IF NOT EXISTS idx_question_visits_visitor "
            "ON question_link_visits(visitor_id,created_at DESC)",
        ),
        "purchases": (
            "CREATE INDEX IF NOT EXISTS idx_purchases_buyer_type_time "
            "ON purchases(buyer_id,type,timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_purchases_receiver_type_time "
            "ON purchases(receiver_id,type,timestamp DESC)",
        ),
        "payment_ledger": (
            "CREATE INDEX IF NOT EXISTS idx_payment_ledger_status_started "
            "ON payment_ledger(status,started_at)",
        ),
        "premium_deliveries": (
            "CREATE INDEX IF NOT EXISTS idx_premium_delivery_status_created "
            "ON premium_deliveries(status,created_at)",
        ),
        "game_duels": (
            "CREATE INDEX IF NOT EXISTS idx_game_duels_status_created "
            "ON game_duels(status,created_at)",
        ),
    }
    for table, table_statements in statements.items():
        if not await _table_exists(conn, table):
            continue
        columns = await _table_columns(conn, table)
        for statement in table_statements:
            # Some additive columns are created lazily by payment modules. Skip an
            # index until every referenced column exists rather than failing startup.
            referenced = {
                token.strip("(),")
                for token in statement.replace(" DESC", "").split()
                if token.strip("(),") in {
                    "sender_id", "receiver_id", "visitor_id", "created_at", "status",
                    "buyer_id", "type", "timestamp", "started_at"
                }
            }
            if referenced.issubset(columns):
                await conn.execute(statement)


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
        await _create_reliability_indexes(conn)
        await conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version,applied_at) VALUES (?,?)",
            (CURRENT_SCHEMA_VERSION, datetime.now().isoformat()),
        )
        await conn.commit()


async def init_db() -> None:
    """Initialize the database without losing legacy matchmaking state."""
    snapshot = await _snapshot_matchmaking(DB_PATH)
    await legacy_repository.init_db()
    await _restore_matchmaking(DB_PATH, snapshot)

from __future__ import annotations

import argparse
import asyncio
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

import aiosqlite

from app.database import schema_migrations


CRITICAL_TABLES = (
    "users",
    "purchases",
    "anonymous_questions",
    "question_link_visits",
    "queues",
    "active_chats",
    "game_duels",
    "payment_ledger",
    "premium_deliveries",
)


async def _table_exists(conn: aiosqlite.Connection, table: str) -> bool:
    row = await (
        await conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
    ).fetchone()
    return row is not None


async def _snapshot(path: Path) -> dict[str, int | None]:
    result: dict[str, int | None] = {}
    async with aiosqlite.connect(path) as conn:
        integrity = await (await conn.execute("PRAGMA integrity_check")).fetchone()
        if not integrity or integrity[0] != "ok":
            raise RuntimeError(f"SQLite integrity_check failed: {integrity}")
        for table in CRITICAL_TABLES:
            if not await _table_exists(conn, table):
                result[table] = None
                continue
            row = await (await conn.execute(f"SELECT COUNT(*) FROM {table}")).fetchone()
            result[table] = int(row[0])
    return result


async def validate(source: Path) -> int:
    if not source.exists() or not source.is_file():
        print(f"ERROR: database not found: {source}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="anonbot-db-check-") as tmp:
        copy_path = Path(tmp) / "bot-copy.db"
        shutil.copy2(source, copy_path)

        before = await _snapshot(copy_path)
        original_path = schema_migrations.DB_PATH
        original_legacy_path = schema_migrations.legacy_repository.DB_PATH
        try:
            schema_migrations.DB_PATH = str(copy_path)
            schema_migrations.legacy_repository.DB_PATH = str(copy_path)
            await schema_migrations.init_db()
        finally:
            schema_migrations.DB_PATH = original_path
            schema_migrations.legacy_repository.DB_PATH = original_legacy_path

        after = await _snapshot(copy_path)

        failures: list[str] = []
        for table in CRITICAL_TABLES:
            old = before[table]
            new = after[table]
            if old is None:
                continue
            if new is None:
                failures.append(f"table disappeared: {table}")
                continue
            if table in {"users", "purchases", "anonymous_questions", "question_link_visits"} and new < old:
                failures.append(f"row loss in {table}: {old} -> {new}")

        async with aiosqlite.connect(copy_path) as conn:
            migration = await (
                await conn.execute(
                    "SELECT MAX(version) FROM schema_migrations"
                )
            ).fetchone()
            reciprocal_errors = await (
                await conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM active_chats a
                    WHERE NOT EXISTS (
                        SELECT 1 FROM active_chats b
                        WHERE b.user_id=a.partner_id AND b.partner_id=a.user_id
                    )
                    """
                )
            ).fetchone()

        print("Database copy validation report")
        print(f"Source: {source}")
        for table in CRITICAL_TABLES:
            print(f"- {table}: {before[table]} -> {after[table]}")
        print(f"- schema version: {migration[0] if migration else None}")
        print(f"- non-reciprocal active chats after migration: {reciprocal_errors[0]}")

        if failures:
            print("FAILED:", file=sys.stderr)
            for failure in failures:
                print(f"- {failure}", file=sys.stderr)
            return 1

        print("OK: migration completed on an isolated copy without critical row loss.")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate AnonBot migrations on an isolated copy of a SQLite database."
    )
    parser.add_argument("database", type=Path, help="Path to the source bot.db")
    args = parser.parse_args()
    try:
        return asyncio.run(validate(args.database.resolve()))
    except (sqlite3.DatabaseError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

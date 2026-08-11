from __future__ import annotations

import html
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from app.core import config
from app.database.repository import DB_PATH
from app.database.schema_migrations import CURRENT_SCHEMA_VERSION


@dataclass(frozen=True)
class HealthCheck:
    name: str
    ok: bool
    detail: str


async def collect_health_checks(bot=None) -> list[HealthCheck]:
    checks: list[HealthCheck] = []
    db_path = Path(DB_PATH)

    try:
        with sqlite3.connect(db_path, timeout=5) as conn:
            integrity = conn.execute("PRAGMA quick_check").fetchone()
            schema_row = conn.execute(
                "SELECT MAX(version) FROM schema_migrations"
            ).fetchone()
        integrity_text = str(integrity[0] if integrity else "unknown")
        schema_version = int(schema_row[0] or 0) if schema_row else 0
        checks.append(HealthCheck("database", integrity_text.lower() == "ok", integrity_text))
        checks.append(
            HealthCheck(
                "schema",
                schema_version == CURRENT_SCHEMA_VERSION,
                f"version={schema_version}/{CURRENT_SCHEMA_VERSION}",
            )
        )
    except Exception as exc:
        checks.append(HealthCheck("database", False, f"{type(exc).__name__}: {exc}"))
        checks.append(HealthCheck("schema", False, "unavailable"))

    try:
        usage = shutil.disk_usage(db_path.parent)
        free_mb = usage.free // (1024 * 1024)
        checks.append(HealthCheck("disk", free_mb >= 256, f"free={free_mb} MiB"))
    except Exception as exc:
        checks.append(HealthCheck("disk", False, f"{type(exc).__name__}: {exc}"))

    if bot is not None:
        try:
            me = await bot.get_me()
            actual = (me.username or "").lstrip("@")
            expected = config.BOT_USERNAME.lstrip("@")
            checks.append(HealthCheck("bot_identity", actual.lower() == expected.lower(), f"@{actual or 'unknown'}"))
        except Exception as exc:
            checks.append(HealthCheck("bot_identity", False, f"{type(exc).__name__}: {exc}"))

        try:
            chat = await bot.get_chat(config.LOG_CHANNEL_ID)
            title = getattr(chat, "title", None) or str(config.LOG_CHANNEL_ID)
            checks.append(HealthCheck("log_channel", True, title))
        except Exception as exc:
            checks.append(HealthCheck("log_channel", False, f"{type(exc).__name__}: {exc}"))

    return checks


def format_health_report(checks: list[HealthCheck]) -> str:
    failed = sum(1 for item in checks if not item.ok)
    header = "✅ <b>Система работает штатно</b>" if failed == 0 else f"⚠️ <b>Проблем: {failed}</b>"
    lines = [header, ""]
    for item in checks:
        icon = "✅" if item.ok else "❌"
        safe_name = html.escape(item.name)
        safe_detail = html.escape(item.detail)
        lines.append(f"{icon} <b>{safe_name}</b>: <code>{safe_detail}</code>")
    return "\n".join(lines)

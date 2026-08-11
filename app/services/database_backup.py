from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.database.repository import DB_PATH


@dataclass(frozen=True)
class BackupResult:
    path: Path
    size_bytes: int
    integrity: str


def _integrity_check(path: Path) -> str:
    with sqlite3.connect(path) as conn:
        row = conn.execute("PRAGMA integrity_check").fetchone()
    return str(row[0] if row else "unknown")


def _record_backup_audit(source_path: Path, result: BackupResult) -> None:
    created_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(source_path, timeout=10) as conn:
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute(
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
        conn.execute(
            "INSERT INTO backup_audit(created_at,path,size_bytes,integrity) VALUES (?,?,?,?)",
            (created_at, str(result.path), int(result.size_bytes), result.integrity),
        )
        conn.commit()


def create_database_backup(
    *,
    source: str | Path = DB_PATH,
    backup_dir: str | Path | None = None,
    keep: int = 30,
) -> BackupResult:
    """Create, verify and audit a consistent SQLite backup.

    The source database may stay open in WAL mode while this runs. The online
    backup API copies committed WAL state into the snapshot. A backup is only
    considered successful after ``PRAGMA integrity_check`` passes and the audit
    row is committed to the source database. Rotation happens last so a failed
    audit can never delete an older known-good snapshot.
    """
    source_path = Path(source)
    if not source_path.exists():
        raise FileNotFoundError(f"Database not found: {source_path}")
    if keep < 1:
        raise ValueError("keep must be >= 1")

    target_dir = Path(backup_dir) if backup_dir else source_path.parent / "backups"
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    target = target_dir / f"bot-{stamp}.db"
    temporary = target.with_suffix(".db.tmp")

    try:
        with sqlite3.connect(source_path) as src, sqlite3.connect(temporary) as dst:
            src.backup(dst)
        integrity = _integrity_check(temporary)
        if integrity.lower() != "ok":
            raise RuntimeError(f"Backup integrity_check failed: {integrity}")
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()

    result = BackupResult(
        path=target,
        size_bytes=target.stat().st_size,
        integrity=integrity,
    )
    _record_backup_audit(source_path, result)

    backups = sorted(
        target_dir.glob("bot-*.db"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for old in backups[keep:]:
        old.unlink(missing_ok=True)

    return result

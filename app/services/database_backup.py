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


def create_database_backup(
    *,
    source: str | Path = DB_PATH,
    backup_dir: str | Path | None = None,
    keep: int = 30,
) -> BackupResult:
    """Create a consistent SQLite backup using the online backup API.

    The source database may stay open in WAL mode while this runs. The backup is
    integrity-checked before it is considered successful and old snapshots are
    rotated only after the new snapshot is valid.
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

    backups = sorted(target_dir.glob("bot-*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in backups[keep:]:
        old.unlink(missing_ok=True)

    return BackupResult(path=target, size_bytes=target.stat().st_size, integrity=integrity)

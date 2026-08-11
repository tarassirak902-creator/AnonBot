from __future__ import annotations

import argparse

from app.services.database_backup import create_database_backup


def main() -> int:
    parser = argparse.ArgumentParser(description="Create and verify a CASPER SQLite backup")
    parser.add_argument("--keep", type=int, default=30, help="number of backups to retain")
    parser.add_argument("--dir", dest="backup_dir", default=None, help="backup directory")
    args = parser.parse_args()

    result = create_database_backup(backup_dir=args.backup_dir, keep=args.keep)
    print(f"backup={result.path} size={result.size_bytes} integrity={result.integrity}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

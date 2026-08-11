# Reliability operations

## Database backups

CASPER now includes an online SQLite backup command that is safe with WAL mode:

```bash
cd /opt/anonymous-chat-bot
python3 tools/backup_db.py --keep 30
```

The backup is written to `data/backups/`, verified with `PRAGMA integrity_check`, and only then old snapshots are rotated.

To enable daily backups with systemd:

```bash
sudo cp deploy/anonymous-chat-bot-backup.service /etc/systemd/system/
sudo cp deploy/anonymous-chat-bot-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now anonymous-chat-bot-backup.timer
sudo systemctl list-timers anonymous-chat-bot-backup.timer
```

Run and inspect a backup manually:

```bash
sudo systemctl start anonymous-chat-bot-backup.service
sudo systemctl status anonymous-chat-bot-backup.service --no-pager
ls -lh /opt/anonymous-chat-bot/data/backups/
```

Before restoring a backup, stop the bot and keep a copy of the current database. Restore only a backup whose integrity check is `ok`.

## Health diagnostics

Administrators can send `/health` to the bot. The report checks:

- SQLite `quick_check`;
- current schema migration version;
- free disk space near the database;
- runtime bot username versus `BOT_USERNAME`;
- access to `LOG_CHANNEL_ID`.

A failed health item is a diagnostic signal, not an automatic repair action.

## Schema migrations

`app/database/schema_migrations.py` is the single migration registry. Every migration has an integer version and must be idempotent. Never reuse or renumber a version that has already reached production. New changes append the next version to `MIGRATIONS` and must have a regression test.

## Deployment checklist

Before restarting production:

```bash
git fetch origin
git checkout main
git pull --ff-only origin main
python3 -m compileall -q app tools run.py
python3 -m pytest -q
python3 tools/backup_db.py --keep 30
sudo systemctl restart anonymous-chat-bot
sudo systemctl status anonymous-chat-bot --no-pager
```

After restart, run `/health` from an administrator account and inspect recent logs if any item is red.

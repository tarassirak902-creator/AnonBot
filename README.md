# AnonBot / CASPER

Telegram bot for anonymous conversations, questions, gifts, Telegram Stars payments, VIP, duels, advertising, referrals, moderation and admin operations.

## Requirements

- Python 3.12+
- SQLite
- Telegram bot token

Required `.env` values:

```env
BOT_TOKEN=...
ADMIN_IDS=123456789
LOG_CHANNEL_ID=-1001234567890
BOT_USERNAME=your_bot_username
```

Install dependencies and run checks:

```bash
python3 -m pip install -r requirements.txt
python3 -m compileall -q app tools run.py tests
python3 -m pytest -q
```

Run locally:

```bash
python3 run.py
```

## Production

The repository contains a systemd unit at `deploy/anonymous-chat-bot.service` and secure deployment documentation in `docs/SECURE_DEPLOYMENT.md`.

Before a production restart, create a verified SQLite backup:

```bash
python3 tools/backup_db.py --keep 30
```

Administrators can use `/health` in Telegram to check the database, migration version, free disk space, bot identity and log-channel access.

Daily backup systemd units are provided in:

- `deploy/anonymous-chat-bot-backup.service`
- `deploy/anonymous-chat-bot-backup.timer`

Operational instructions, backup/restore guidance and the deployment checklist are in `docs/RELIABILITY_OPERATIONS.md`.

## Database migrations

Versioned schema changes live in `app/database/schema_migrations.py`. Migration numbers are append-only and applied sequentially. Never reuse a version that has already reached production.

## CI

GitHub Actions compiles the Python sources, imports the application and runs the full pytest suite. Changes should not be merged while Quality checks are red.

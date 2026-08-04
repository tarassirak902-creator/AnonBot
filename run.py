from __future__ import annotations

import asyncio
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"


def ensure_env() -> None:
    if ENV_FILE.exists() and "BOT_TOKEN=" in ENV_FILE.read_text(encoding="utf-8"):
        token_line = next((x for x in ENV_FILE.read_text(encoding="utf-8").splitlines() if x.startswith("BOT_TOKEN=")), "")
        if token_line.split("=", 1)[-1].strip():
            return

    print("Первый запуск. Вставьте токен бота от @BotFather.")
    token = input("BOT_TOKEN: ").strip()
    if not token:
        raise SystemExit("Токен не указан.")
    admin_ids = input("ADMIN_IDS (ваш Telegram ID, можно несколько через запятую): ").strip()
    log_channel = input("LOG_CHANNEL_ID (например -1001234567890): ").strip()
    ENV_FILE.write_text(
        f"BOT_TOKEN={token}\nADMIN_IDS={admin_ids}\nLOG_CHANNEL_ID={log_channel}\n",
        encoding="utf-8",
    )
    print("Настройки сохранены в .env")


if __name__ == "__main__":
    ensure_env()
    from app.main import main
    asyncio.run(main())

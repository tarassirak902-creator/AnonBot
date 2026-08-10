from __future__ import annotations

import asyncio
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
_REQUIRED_KEYS = ("BOT_TOKEN", "ADMIN_IDS", "LOG_CHANNEL_ID", "BOT_USERNAME")


def _read_env() -> dict[str, str]:
    if not ENV_FILE.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def ensure_env() -> None:
    values = _read_env()
    if all(values.get(key, "").strip() for key in _REQUIRED_KEYS):
        return

    print("Первый запуск или неполный .env. Заполните обязательные параметры.")
    prompts = {
        "BOT_TOKEN": "BOT_TOKEN (токен от @BotFather): ",
        "ADMIN_IDS": "ADMIN_IDS (Telegram ID, можно несколько через запятую): ",
        "LOG_CHANNEL_ID": "LOG_CHANNEL_ID (например -1001234567890): ",
        "BOT_USERNAME": "BOT_USERNAME (username бота без или с @): ",
    }
    for key in _REQUIRED_KEYS:
        if values.get(key, "").strip():
            continue
        value = input(prompts[key]).strip()
        if not value:
            raise SystemExit(f"{key} не указан.")
        values[key] = value.lstrip("@") if key == "BOT_USERNAME" else value

    preserved: list[str] = []
    if ENV_FILE.exists():
        required = set(_REQUIRED_KEYS)
        for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            stripped = raw_line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                if key in required:
                    continue
            preserved.append(raw_line)

    required_lines = [f"{key}={values[key]}" for key in _REQUIRED_KEYS]
    output = "\n".join(required_lines + ([""] + preserved if preserved else [])) + "\n"
    ENV_FILE.write_text(output, encoding="utf-8")
    print("Настройки сохранены в .env")


if __name__ == "__main__":
    ensure_env()
    from app.main import main
    asyncio.run(main())

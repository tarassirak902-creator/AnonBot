from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Не задана обязательная переменная окружения {name} в файле .env")
    return value


def _parse_admin_ids(value: str) -> list[int]:
    result: list[int] = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            result.append(int(item))
        except ValueError as exc:
            raise RuntimeError(f"Некорректный ADMIN_IDS: {item!r} не является числом") from exc
    if not result:
        raise RuntimeError("ADMIN_IDS должен содержать хотя бы один Telegram user ID")
    return result


def _parse_int_env(name: str) -> int:
    value = _required_env(name)
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"Переменная {name} должна быть целым числом") from exc


BOT_TOKEN = _required_env("BOT_TOKEN")
ADMIN_IDS = _parse_admin_ids(_required_env("ADMIN_IDS"))
LOG_CHANNEL_ID = _parse_int_env("LOG_CHANNEL_ID")
BOT_USERNAME = _required_env("BOT_USERNAME").lstrip("@")

DEFAULT_REVEAL_COST = "15"
DEFAULT_WELCOME_TEXT = "👻 Добро пожаловать в CASPER! Выберите нужный раздел ниже."

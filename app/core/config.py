import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("Не задан BOT_TOKEN. Создайте файл .env рядом с config.py.")

def _parse_admin_ids(value: str) -> list[int]:
    result = []
    for item in value.split(","):
        item = item.strip()
        if item:
            result.append(int(item))
    return result

ADMIN_IDS = _parse_admin_ids(os.getenv("ADMIN_IDS", "8517077158"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "-1003944289895"))
BOT_USERNAME = os.getenv("BOT_USERNAME", "").strip().lstrip("@")

DEFAULT_REVEAL_COST = "15"
DEFAULT_WELCOME_TEXT = "👻 Добро пожаловать в CASPER! Выберите нужный раздел ниже."

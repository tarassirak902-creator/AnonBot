from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from app.core import keyboards
from . import shared


MAIN_LABELS = {
    "chat": "💬 Чат",
    "questions": "❓ Вопросы",
    "games": "🎮 Игры",
    "profile": "👤 Профиль",
    "friends": "🎁 Друзья",
    "daily": "☀️ Мой день",
    "more": "✨ Ещё",
    "ads": "📣 Реклама",
    "admin": "⚙️ Админка",
}

CHAT_LABELS = {
    "next": "➡️ Новый",
    "end": "⏹ Завершить",
    "gift": "🎁 Подарок",
    "reveal": "👤 Раскрыть",
    "duel": "🎮 Дуэль",
    "complaint": "🚨 Жалоба",
}


def _reply(rows: list[list[KeyboardButton]]) -> ReplyKeyboardMarkup:
    """Build a keyboard that stays available but can still be collapsed manually."""
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=True,
        input_field_placeholder="Выберите раздел",
    )


def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=MAIN_LABELS["chat"])],
        [
            KeyboardButton(text=MAIN_LABELS["questions"]),
            KeyboardButton(text=MAIN_LABELS["profile"]),
        ],
        [
            KeyboardButton(text=MAIN_LABELS["games"]),
            KeyboardButton(text=MAIN_LABELS["friends"]),
        ],
        [
            KeyboardButton(text=MAIN_LABELS["daily"]),
            KeyboardButton(text=MAIN_LABELS["admin"] if is_admin else MAIN_LABELS["more"]),
        ],
    ]
    return _reply(rows)


def main_menu_with_question(display_name: str, is_admin: bool = False) -> ReplyKeyboardMarkup:
    return _reply([
        [KeyboardButton(text=f"❓ Написать {display_name} анонимно")],
        *main_menu(is_admin).keyboard,
    ])


def chat_menu() -> ReplyKeyboardMarkup:
    return _reply([
        [KeyboardButton(text=CHAT_LABELS["next"]), KeyboardButton(text=CHAT_LABELS["end"])],
        [KeyboardButton(text=CHAT_LABELS["gift"]), KeyboardButton(text=CHAT_LABELS["reveal"])],
        [KeyboardButton(text=CHAT_LABELS["duel"]), KeyboardButton(text=CHAT_LABELS["complaint"])],
    ])


def install_minimal_keyboards() -> None:
    """Install canonical compact keyboards before handler modules import shared names."""
    for namespace in (keyboards, shared):
        namespace.main_menu = main_menu
        namespace.main_menu_with_question = main_menu_with_question
        namespace.chat_menu = chat_menu

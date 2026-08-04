from pathlib import Path

from app.handlers.minimal_keyboard_ui import CHAT_LABELS, MAIN_LABELS, chat_menu, main_menu


ALIASES = Path("app/handlers/visible_button_aliases.py").read_text(encoding="utf-8")
INIT = Path("app/handlers/__init__.py").read_text(encoding="utf-8")


def _labels(keyboard) -> list[str]:
    return [button.text for row in keyboard.keyboard for button in row]


def test_main_menu_uses_compact_one_or_two_word_labels() -> None:
    labels = _labels(main_menu(False))
    assert labels == [
        MAIN_LABELS["chat"],
        MAIN_LABELS["questions"],
        MAIN_LABELS["games"],
        MAIN_LABELS["profile"],
        MAIN_LABELS["friends"],
        MAIN_LABELS["ads"],
    ]
    assert all(len(label.split()) <= 2 for label in labels)


def test_admin_main_menu_uses_compact_admin_label() -> None:
    labels = _labels(main_menu(True))
    assert MAIN_LABELS["admin"] in labels
    assert MAIN_LABELS["ads"] not in labels


def test_chat_menu_uses_compact_labels() -> None:
    labels = _labels(chat_menu())
    assert labels == list(CHAT_LABELS.values())
    assert all(len(label.split()) <= 2 for label in labels)


def test_every_compact_label_has_an_explicit_route() -> None:
    for label in (*MAIN_LABELS.values(), *CHAT_LABELS.values()):
        assert f'"{label}"' in ALIASES


def test_legacy_labels_remain_supported() -> None:
    for label in (
        "🚀 Начать общение",
        "❓ Анонимные вопросы",
        "🎁 Пригласить друга",
        "📣 Разместить рекламу",
        "⚙️ Панель управления",
        "➡️ Новый собеседник",
        "❌ Завершить диалог",
        "👤 Кто это?",
    ):
        assert f'"{label}"' in ALIASES


def test_minimal_keyboards_install_before_handler_imports() -> None:
    assert INIT.index("install_minimal_keyboards()") < INIT.index("from . import questions")

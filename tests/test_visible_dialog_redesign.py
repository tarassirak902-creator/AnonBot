from pathlib import Path

KEYBOARDS = Path("app/core/keyboards.py").read_text(encoding="utf-8")
SEARCH_UI = Path("app/handlers/search_ui.py").read_text(encoding="utf-8")
DIALOG_UI = Path("app/handlers/dialog_ui.py").read_text(encoding="utf-8")
CHAT_ACTIONS = Path("app/handlers/chat_actions_ui.py").read_text(encoding="utf-8")
PROFILE_GAMES = Path("app/handlers/profile_games_ui.py").read_text(encoding="utf-8")


def test_chat_menu_uses_compact_visible_controls() -> None:
    for label in ("➡️ Новый собеседник", "⏹ Завершить", "🎁 Подарок", "👤 Кто это?", "🎮 Дуэль", "🚨 Жалоба"):
        assert label in KEYBOARDS


def test_new_and_legacy_search_labels_are_supported() -> None:
    assert '"🚀 Начать общение", "💬 Найти собеседника"' in SEARCH_UI


def test_new_and_legacy_dialog_end_labels_are_supported() -> None:
    assert '"➡️ Новый собеседник", "➡️ Следующий собеседник"' in DIALOG_UI
    assert '"⏹ Завершить", "❌ Завершить диалог"' in DIALOG_UI


def test_secondary_dialog_actions_keep_legacy_compatibility() -> None:
    combined = CHAT_ACTIONS + PROFILE_GAMES
    for new_label, legacy_label in (
        ("🎁 Подарок", "🎁 Подарить подарок"),
        ("👤 Кто это?", "⭐ Кто собеседник"),
        ("🎮 Дуэль", "⚔️ Играть с собеседником"),
        ("🚨 Жалоба", "⚠️ Пожаловаться"),
    ):
        assert new_label in combined
        assert legacy_label in combined


def test_search_and_dialog_copy_are_visibly_distinct() -> None:
    assert "🚀 Поиск запущен" in SEARCH_UI
    assert "✨ Собеседник найден" in SEARCH_UI
    assert "🔄 Ищу нового собеседника" in DIALOG_UI
    assert "👋 Диалог завершён" in DIALOG_UI

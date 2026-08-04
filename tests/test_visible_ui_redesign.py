from app.core.keyboards import main_menu


def _labels(keyboard) -> list[str]:
    return [button.text for row in keyboard.keyboard for button in row]


def test_primary_menu_has_visible_new_labels() -> None:
    labels = _labels(main_menu(False))
    assert labels[0] == "🚀 Начать общение"
    assert "❓ Анонимные вопросы" in labels
    assert "🎮 Игры" in labels
    assert "👤 Профиль" in labels
    assert "🎁 Пригласить друга" in labels
    assert "📣 Разместить рекламу" in labels


def test_admin_menu_has_visible_control_panel_label() -> None:
    labels = _labels(main_menu(True))
    assert "⚙️ Панель управления" in labels
    assert "📣 Разместить рекламу" not in labels


def test_new_and_legacy_labels_are_supported() -> None:
    menus = open("app/handlers/menus.py", encoding="utf-8").read()
    aliases = open("app/handlers/visible_button_aliases.py", encoding="utf-8").read()
    keyboards = open("app/core/keyboards.py", encoding="utf-8").read()
    source = menus + aliases + keyboards
    assert '"🚀 Начать общение"' in source
    assert '"💬 Найти собеседника"' in source
    assert '"👤 Профиль"' in source
    assert '"👤 Моя анкета"' in source
    assert '"🎮 Игры"' in source
    assert '"🎮 Мини-игры"' in source
    assert '"⚙️ Панель управления"' in source


def test_start_screen_describes_new_information_architecture() -> None:
    source = open("app/handlers/commands.py", encoding="utf-8").read()
    assert "Что хотите сделать?" in source
    assert "Главное действие всегда находится на первой кнопке" in source
    assert '"🎁 Пригласить друга"' in source

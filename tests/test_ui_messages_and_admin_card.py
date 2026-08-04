from app.core.ui_messages import confirm, status
from app.handlers import shared
from app.handlers.admin_card_ui import build_compact_admin_user_card, install_admin_card_ui


def test_status_uses_consistent_icon_and_escapes_dynamic_text() -> None:
    text = status("error", "Не удалось выполнить", "Имя: <admin>")

    assert text.startswith("<b>❌ Не удалось выполнить</b>")
    assert "&lt;admin&gt;" in text
    assert "<admin>" not in text


def test_confirmation_distinguishes_dangerous_actions() -> None:
    normal = confirm("Подтвердите", "Продолжить операцию?")
    danger = confirm("Удалить данные", "Это действие нельзя отменить.", danger=True)

    assert normal.startswith("<b>❓ Подтвердите</b>")
    assert danger.startswith("<b>⚠️ Удалить данные</b>")
    assert "Подтвердите действие кнопкой ниже" in danger


def test_compact_admin_renderer_is_installed_on_shared_boundary() -> None:
    install_admin_card_ui()

    assert shared.admin_user_card is build_compact_admin_user_card

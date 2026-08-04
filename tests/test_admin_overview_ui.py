from app.core.ui_labels import ButtonText
from app.handlers.admin_overview_ui import (
    admin_home_text,
    admin_statistics_text,
    admin_users_keyboard,
)


def _stats() -> dict:
    return {
        "total_users": 10,
        "new_today": 2,
        "active_vip_users": 1,
        "vip_purchases": 3,
        "queue_count": 4,
        "active_chats": 5,
        "total_gifts_sent": 6,
        "gifts_today": 7,
        "total_stars": 8,
        "reveal_count": 9,
        "total_complaints": 10,
    }


def test_admin_home_uses_canonical_copy() -> None:
    text = admin_home_text()
    assert "Панель управления" in text
    assert "Выберите раздел" in text


def test_admin_statistics_is_sectioned_and_compact() -> None:
    text = admin_statistics_text(_stats())
    assert "Пользователи" in text
    assert "Общение" in text
    assert "Активность" in text
    assert "━━━━━━━━" not in text


def test_admin_users_keyboard_uses_canonical_back_button() -> None:
    keyboard = admin_users_keyboard()
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    assert ButtonText.BACK in labels
    assert all(len(row) <= 2 for row in keyboard.inline_keyboard)

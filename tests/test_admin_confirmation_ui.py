from app.core.ui_labels import ButtonText
from app.handlers.admin_confirmation_ui import _confirmation_keyboard


def _labels(keyboard):
    return [button.text for row in keyboard.inline_keyboard for button in row]


def _callbacks(keyboard):
    return [button.callback_data for row in keyboard.inline_keyboard for button in row]


def test_confirmation_keyboard_uses_canonical_cancel() -> None:
    keyboard = _confirmation_keyboard(
        confirm_text="⛔ Заблокировать",
        confirm_callback="admin_do_ban_42",
        user_id=42,
    )
    assert _labels(keyboard) == ["⛔ Заблокировать", ButtonText.CANCEL]


def test_confirmation_keyboard_preserves_admin_callbacks() -> None:
    keyboard = _confirmation_keyboard(
        confirm_text="✅ Ограничить на 24 часа",
        confirm_callback="admin_do_mute_42",
        user_id=42,
    )
    assert _callbacks(keyboard) == ["admin_do_mute_42", "admin_user_card_42"]


def test_confirmation_keyboard_is_compact() -> None:
    keyboard = _confirmation_keyboard(
        confirm_text="✅ Выдать VIP",
        confirm_callback="admin_give_vip_42",
        user_id=42,
    )
    assert len(keyboard.inline_keyboard) == 1
    assert len(keyboard.inline_keyboard[0]) == 2

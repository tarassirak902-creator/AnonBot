from app.core.ui_labels import ButtonText
from app.handlers.service_menu import ABOUT_TEXT, PRIVACY_TEXT, dismiss_kb


def test_service_copy_uses_compact_titles() -> None:
    assert ABOUT_TEXT.startswith("<b>👻 О CASPER GO</b>")
    assert PRIVACY_TEXT.startswith("<b>🔐 Конфиденциальность</b>")
    assert "━━━━━━━━" not in ABOUT_TEXT
    assert "━━━━━━━━" not in PRIVACY_TEXT


def test_service_dismiss_button_is_canonical() -> None:
    keyboard = dismiss_kb()
    assert keyboard.inline_keyboard[-1][0].text == ButtonText.CLOSE
    assert keyboard.inline_keyboard[-1][0].callback_data == "service_message_delete"

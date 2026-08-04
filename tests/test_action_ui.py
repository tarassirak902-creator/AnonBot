from app.core.action_ui import (
    confirmation_keyboard,
    confirmation_screen,
    payment_description,
    withdraw_screen,
)


def test_confirmation_screen_escapes_user_text() -> None:
    text = confirmation_screen("Удалить <запись>", "Пользователь & данные", danger=True)
    assert "&lt;запись&gt;" in text
    assert "Пользователь &amp; данные" in text
    assert "Подтвердите действие" in text


def test_confirmation_keyboard_is_compact() -> None:
    keyboard = confirmation_keyboard("✅ Да", "confirm:test", "cancel:test")
    assert len(keyboard.inline_keyboard) == 1
    assert len(keyboard.inline_keyboard[0]) == 2
    assert keyboard.inline_keyboard[0][0].callback_data == "confirm:test"
    assert keyboard.inline_keyboard[0][1].callback_data == "cancel:test"


def test_payment_description_has_consistent_sentences() -> None:
    description = payment_description("VIP CASPER", "Скидка 30%", "30 дней")
    assert description == "VIP CASPER. 30 дней. Скидка 30%."


def test_withdraw_screen_contains_balance_and_hint() -> None:
    text = withdraw_screen(125)
    assert "125 ⭐" in text
    assert "не может превышать" in text

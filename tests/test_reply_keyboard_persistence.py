from app.handlers.minimal_keyboard_ui import chat_menu, main_menu, main_menu_with_question


def test_all_reply_keyboards_stay_available_without_one_time_close() -> None:
    keyboards = (
        main_menu(),
        main_menu(is_admin=True),
        main_menu_with_question("Гостю"),
        chat_menu(),
    )
    for keyboard in keyboards:
        assert keyboard.resize_keyboard is True
        assert keyboard.one_time_keyboard is False
        assert keyboard.is_persistent is True

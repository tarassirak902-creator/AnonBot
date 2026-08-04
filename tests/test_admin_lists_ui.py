from app.handlers.admin_lists_ui import _back_to_users, _user_label


def test_admin_lists_use_canonical_back_button() -> None:
    keyboard = _back_to_users()
    button = keyboard.inline_keyboard[0][0]
    assert button.text == "⬅️ Назад"
    assert button.callback_data == "admin_back_to_users"


def test_admin_user_label_is_compact_and_escaped() -> None:
    label = _user_label("<Иван>", None, "test&name")
    assert "&lt;Иван&gt;" in label
    assert "@test&amp;name" in label
    assert " · " in label


def test_admin_list_module_preserves_withdraw_callbacks() -> None:
    source = __import__("inspect").getsource(__import__("app.handlers.admin_lists_ui", fromlist=["*"]))
    assert "withdraw_approve_" in source
    assert "withdraw_reject_" in source
    assert "admin_warned_list" in source
    assert "admin_restricted_list" in source

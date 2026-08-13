from pathlib import Path


COMMANDS = Path("app/handlers/commands.py").read_text(encoding="utf-8")
DIALOG = Path("app/handlers/dialog_ui.py").read_text(encoding="utf-8")
INIT = Path("app/handlers/__init__.py").read_text(encoding="utf-8")


def test_back_exit_delegates_to_canonical_dialog_lifecycle() -> None:
    handler = COMMANDS.split("async def back_to_main", 1)[1].split('@router.message(Command("paysupport"))', 1)[0]
    assert "await _finish_dialog(message, find_next=False)" in handler
    assert "add_completed_chat_time" not in handler
    assert "db.end_chat" not in handler
    assert "send_ads_to_dialog_users" not in handler


def test_plain_start_uses_canonical_lifecycle_without_duplicate_result_card() -> None:
    start = COMMANDS.split("async def cmd_start", 1)[1].split("async def invite_friend", 1)[0]
    assert "await _finish_dialog(message, find_next=False, show_user_result=False)" in start
    assert "add_completed_chat_time" not in start
    assert "db.end_chat" not in start


def test_question_deeplink_does_not_end_active_dialog() -> None:
    start = COMMANDS.split("async def cmd_start", 1)[1].split("async def invite_friend", 1)[0]
    guard = start.index("if ask_token and await db.get_partner(user_id):")
    canonical_exit = start.index("await _finish_dialog(message, find_next=False, show_user_result=False)")
    assert guard < canonical_exit


def test_canonical_lifecycle_supports_quiet_parent_flows() -> None:
    assert "show_user_result: bool = True" in DIALOG
    assert "if show_user_result:" in DIALOG
    assert "await end_chat_with_accounting(user_id)" in DIALOG
    assert "await _send_rating_prompts" in DIALOG
    assert "await _record_dialog_completion" in DIALOG


def test_dialog_ui_stays_registered_before_legacy_menus() -> None:
    assert INIT.index("from . import dialog_ui") < INIT.index("from . import menus")

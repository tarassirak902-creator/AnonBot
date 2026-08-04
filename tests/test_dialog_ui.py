from pathlib import Path


SOURCE = Path("app/handlers/dialog_ui.py").read_text(encoding="utf-8")
INIT_SOURCE = Path("app/handlers/__init__.py").read_text(encoding="utf-8")


def test_dialog_handlers_keep_new_and_legacy_reply_button_contracts() -> None:
    assert '"➡️ Новый собеседник"' in SOURCE
    assert '"➡️ Следующий собеседник"' in SOURCE
    assert '"⏹ Завершить"' in SOURCE
    assert '"❌ Завершить диалог"' in SOURCE


def test_dialog_copy_uses_shared_screen_format() -> None:
    assert 'screen(' in SOURCE
    assert '"👋 Диалог завершён"' in SOURCE
    assert '"🏠 Вы уже в главном меню"' in SOURCE
    assert '"🔄 Ищем нового собеседника"' in SOURCE


def test_dialog_logic_keeps_cleanup_and_followup_calls() -> None:
    for call in (
        "cancel_search_timer(user_id)",
        "await db.end_chat(user_id)",
        "cancel_inactivity_timer(user_id, partner_id)",
        "await send_ads_to_dialog_users(",
        "await notify_pending_question_activity(message.bot, user_id)",
        "await start_searching(message)",
    ):
        assert call in SOURCE


def test_dialog_ui_is_registered_before_legacy_menus() -> None:
    assert INIT_SOURCE.index("from . import dialog_ui") < INIT_SOURCE.index("from . import menus")

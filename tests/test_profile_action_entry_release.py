from pathlib import Path


def test_profile_action_entry_is_registered_first() -> None:
    source = Path("app/handlers/__init__.py").read_text(encoding="utf-8")
    assert "from . import profile_action_entry" in source
    assert source.index("from . import profile_action_entry") < source.index("from . import engagement_ui")
    assert source.index("from . import profile_action_entry") < source.index("from . import community_ui")


def test_all_visible_profile_callbacks_have_safe_entry_handlers() -> None:
    source = Path("app/handlers/profile_action_entry.py").read_text(encoding="utf-8")
    for callback_data in (
        "engagement_missions",
        "user_activity_center",
        "community_dialog_history",
        "community_connections",
        "profile_hub_activity",
        "profile_hub_rewards",
        "profile_hub_social",
        "profile_hub_premium",
    ):
        assert callback_data in source
    assert "_safe_edit" in source
    assert "_table_exists" in source
    assert "load_daily_missions" in source
    assert "claim_daily_mission" in source


def test_profile_actions_keep_privacy_contract() -> None:
    source = Path("app/handlers/profile_action_entry.py").read_text(encoding="utf-8")
    assert "Сообщения и Telegram-профили не сохраняются" in source
    assert "Взаимных контактов" in source
    assert "message.text" not in source

from pathlib import Path


def test_state_changing_handlers_use_shared_action_flow() -> None:
    expected = {
        "app/handlers/platform_progress_ui.py": "progress_weekly_claim",
        "app/handlers/platform_missions_ui.py": "mission_reward_claim",
        "app/handlers/platform_personal_goals_ui.py": "personal_goal_claim",
        "app/handlers/platform_dashboard_ui.py": "community_contact_remove",
        "app/handlers/platform_growth_ui.py": "growth_daily_claim",
        "app/handlers/platform_reactivation_ui.py": "reactivation_claim",
        "app/handlers/platform_social_ui.py": "notifications_read_callback",
    }
    for filename, handler_name in expected.items():
        source = Path(filename).read_text(encoding="utf-8")
        assert "run_state_action" in source, filename
        assert handler_name in source, filename


def test_growth_and_comeback_ui_do_not_credit_balance_separately() -> None:
    for filename in (
        "app/handlers/platform_growth_ui.py",
        "app/handlers/platform_reactivation_ui.py",
    ):
        source = Path(filename).read_text(encoding="utf-8")
        assert "add_user_balance" not in source, filename


def test_notifications_read_all_has_single_action_flow_owner() -> None:
    source = Path("app/handlers/platform_social_ui.py").read_text(encoding="utf-8")
    handler = source.split("async def notifications_read_callback", 1)[1]
    assert "run_state_action" in handler
    assert "callback.answer(" not in handler

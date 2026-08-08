from pathlib import Path


def test_state_changing_handlers_use_shared_action_flow() -> None:
    expected = {
        "app/handlers/platform_progress_ui.py": "progress_weekly_claim",
        "app/handlers/platform_missions_ui.py": "mission_reward_claim",
        "app/handlers/platform_personal_goals_ui.py": "personal_goal_claim",
        "app/handlers/platform_dashboard_ui.py": "community_contact_remove",
    }
    for filename, handler_name in expected.items():
        source = Path(filename).read_text(encoding="utf-8")
        assert "run_state_action" in source, filename
        assert handler_name in source, filename

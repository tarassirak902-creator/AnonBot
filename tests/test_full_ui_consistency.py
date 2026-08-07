from pathlib import Path


HANDLERS = Path("app/handlers")
TARGETS = (
    "platform_progress_ui.py",
    "platform_missions_ui.py",
    "platform_personal_goals_ui.py",
    "platform_reactivation_ui.py",
)


def _source(name: str) -> str:
    return (HANDLERS / name).read_text(encoding="utf-8")


def test_retention_screens_use_unified_renderer() -> None:
    for name in TARGETS:
        source = _source(name)
        assert "from app.core.ui_renderer import render_callback, render_message" in source
        assert "callback.message.answer(" not in source
        assert "except Exception:\n        pass" not in source


def test_refresh_routes_render_in_place() -> None:
    expected = {
        "platform_progress_ui.py": 'F.data == "progress_center"',
        "platform_missions_ui.py": 'F.data == "season_missions"',
        "platform_personal_goals_ui.py": 'F.data == "personal_goals"',
        "platform_reactivation_ui.py": 'F.data == "reactivation_center"',
    }
    for name, route in expected.items():
        source = _source(name)
        assert route in source
        assert "await render_callback(callback, text" in source


def test_reward_claims_answer_once_then_render_same_message() -> None:
    for name in TARGETS:
        source = _source(name)
        assert "if callback.message is not None:" in source
        assert "await render_message(callback.message, text" in source


def test_admin_retention_metrics_use_same_renderer() -> None:
    callbacks = {
        "platform_progress_ui.py": "admin_progress_metrics",
        "platform_missions_ui.py": "admin_mission_metrics",
        "platform_personal_goals_ui.py": "admin_personal_goals",
        "platform_reactivation_ui.py": "admin_reactivation_metrics",
    }
    for name, callback_name in callbacks.items():
        source = _source(name)
        assert callback_name in source
        assert 'answer_text="Обновлено"' in source

from pathlib import Path


def test_profile_uses_runtime_safe_insight_fields() -> None:
    source = Path("app/handlers/profile_view.py").read_text(encoding="utf-8")
    assert 'getattr(insights, "completed_chats", 0)' in source
    assert 'getattr(insights, "referrals_total", 0)' in source
    assert 'getattr(insights, "days_in_bot", 0)' in source


def test_profile_insights_defines_dashboard_fields() -> None:
    source = Path("app/services/profile_insights.py").read_text(encoding="utf-8")
    assert "completed_chats: int = 0" in source
    assert "referrals_total: int = 0" in source


def test_community_ui_keeps_only_mutual_contacts() -> None:
    handlers = Path("app/handlers/__init__.py").read_text(encoding="utf-8")
    ui = Path("app/handlers/community_ui.py").read_text(encoding="utf-8")
    repository = Path("app/database/community_repository.py").read_text(encoding="utf-8")
    profile = Path("app/handlers/profile_view.py").read_text(encoding="utf-8")

    assert "from . import community_ui" in handlers
    assert "community_connections" in ui
    assert "community_reconnect_toggle" in ui
    assert "request_reconnect" in repository
    assert "🎯 Интересы" not in profile
    assert "community_language:" not in ui
    assert "community_interest:" not in ui
    assert "interests_json" not in repository

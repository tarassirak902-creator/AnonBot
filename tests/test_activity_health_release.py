from pathlib import Path


def test_activity_and_health_handlers_are_registered() -> None:
    handlers = Path("app/handlers/__init__.py").read_text(encoding="utf-8")
    ui = Path("app/handlers/activity_health_ui.py").read_text(encoding="utf-8")
    assert "from . import activity_health_ui" in handlers
    assert 'F.data == "user_activity_center"' in ui
    assert '"admin_platform_health"' in ui
    assert '"admin_platform_health_from_growth"' in ui
    assert '"admin_platform_health_from_ops"' in ui


def test_profile_exposes_activity_center() -> None:
    source = Path("app/handlers/profile_view.py").read_text(encoding="utf-8")
    assert "⚡ Активность" in source
    assert 'callback_data="user_activity_center"' in source


def test_admin_center_exposes_contextual_platform_health() -> None:
    source = Path("app/handlers/platform_dashboard_ui.py").read_text(encoding="utf-8")
    assert "🩺 Здоровье" in source
    assert 'health_callback = "admin_platform_health_from_ops"' in source
    assert 'health_callback = "admin_platform_health_from_ops_growth"' in source


def test_health_service_detects_queue_and_chat_anomalies() -> None:
    source = Path("app/services/activity_health.py").read_text(encoding="utf-8")
    assert "queue_stale" in source
    assert "one_sided_chats" in source
    assert "stale_chats" in source
    assert "route_errors_24h" in source
    assert "LEFT JOIN active_chats" in source


def test_activity_report_does_not_analyze_message_text() -> None:
    source = Path("app/services/activity_health.py").read_text(encoding="utf-8")
    forbidden = ("message_text", "content_text", "SELECT text FROM", "SELECT caption FROM")
    assert not any(token in source for token in forbidden)

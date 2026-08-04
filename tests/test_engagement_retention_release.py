from pathlib import Path


def test_engagement_service_has_atomic_daily_claims() -> None:
    source = Path("app/services/engagement_service.py").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS daily_mission_claims" in source
    assert "BEGIN IMMEDIATE" in source
    assert "INSERT OR IGNORE INTO daily_mission_claims" in source
    assert "stars_balance=COALESCE(stars_balance,0)+?" in source


def test_profile_exposes_daily_missions() -> None:
    source = Path("app/handlers/profile_view.py").read_text(encoding="utf-8")
    assert 'text="🎯 Задания"' in source
    assert 'callback_data="engagement_missions"' in source


def test_engagement_and_retention_routes_are_registered() -> None:
    handlers = Path("app/handlers/__init__.py").read_text(encoding="utf-8")
    ui = Path("app/handlers/engagement_ui.py").read_text(encoding="utf-8")
    assert "from . import engagement_ui" in handlers
    assert "engagement_mission_claim:" in ui
    assert "admin_retention_dashboard" in ui
    assert "📈 Удержание и вовлечённость" in ui


def test_retention_metrics_do_not_read_message_content() -> None:
    service = Path("app/services/engagement_service.py").read_text(encoding="utf-8")
    assert "message_text" not in service
    assert "SELECT text" not in service
    assert "load_retention_snapshot" in service

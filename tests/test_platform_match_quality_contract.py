from pathlib import Path


def test_match_quality_repository_is_privacy_safe_and_atomic():
    source = Path("app/database/platform_match_quality_repository.py").read_text(encoding="utf-8")
    assert "BEGIN IMMEDIATE" in source
    assert "PRIMARY KEY(dialog_key, rater_id)" in source
    assert "message.text" not in source
    assert "caption" not in source


def test_matchmaking_uses_quality_as_soft_signal_with_fifo_fallback():
    source = Path("app/database/matchmaking_repository.py").read_text(encoding="utf-8")
    assert "LEFT JOIN match_quality" in source
    assert "ABS(COALESCE(mq.score,50)-?)" in source
    assert "q.created_at ASC" in source
    assert "q.rowid ASC" in source


def test_rating_handler_feeds_quality_ledger():
    source = Path("app/handlers/platform_automation_ui.py").read_text(encoding="utf-8")
    assert "record_match_quality_rating" in source
    assert "pending.dialog_key" in source


def test_match_quality_admin_route_is_registered_before_legacy_handlers():
    handlers = Path("app/handlers/__init__.py").read_text(encoding="utf-8")
    assert "from . import platform_match_quality_ui" in handlers
    assert handlers.index("platform_match_quality_ui") < handlers.index("callbacks_admin")


def test_growth_admin_has_quality_entry():
    source = Path("app/handlers/platform_growth_ui.py").read_text(encoding="utf-8")
    assert 'callback_data="admin_match_quality"' in source
    assert "🧠 Качество" in source

from pathlib import Path


def test_history_and_moderation_module_is_registered() -> None:
    handlers = Path("app/handlers/__init__.py").read_text(encoding="utf-8")
    source = Path("app/handlers/history_moderation_ui.py").read_text(encoding="utf-8")
    assert "from . import history_moderation_ui" in handlers
    assert "community_dialog_history" in source
    assert "admin_complaints_dashboard" in source
    assert "admin_complaint_review:" in source


def test_profile_has_dialog_history_button() -> None:
    source = Path("app/handlers/profile_view.py").read_text(encoding="utf-8")
    assert "🕘 История" in source
    assert 'callback_data="community_dialog_history"' in source


def test_complaint_review_queue_is_non_destructive() -> None:
    source = Path("app/handlers/history_moderation_ui.py").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS complaint_reviews" in source
    assert "INSERT OR REPLACE INTO complaint_reviews" in source
    assert "UPDATE users SET blocked" not in source
    assert "DELETE FROM complaints" not in source


def test_dialog_history_does_not_expose_profiles_or_messages() -> None:
    source = Path("app/handlers/history_moderation_ui.py").read_text(encoding="utf-8")
    assert "Содержимое переписки и Telegram-профили не сохраняются" in source
    assert "SELECT partner_id,last_chat_at FROM recent_partners" in source

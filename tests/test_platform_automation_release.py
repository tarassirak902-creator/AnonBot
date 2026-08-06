from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_automation_repository_uses_single_use_expiring_tokens():
    source = read("app/database/platform_automation_repository.py")
    assert "pending_dialog_ratings" in source
    assert "consumed_at IS NULL" in source
    assert "expires_at >= ?" in source
    assert "BEGIN IMMEDIATE" in source
    assert "secrets.token_urlsafe" in source


def test_rating_callback_does_not_trust_partner_id_from_callback_data():
    source = read("app/handlers/platform_automation_ui.py")
    assert 'callback_data=f"dialog_rate:1:{pending.token}"' in source
    assert "consume_rating_token(token, callback.from_user.id)" in source
    assert "pending.rated_user_id" in source
    assert "dialog_rate:{pending.rated_user_id}" not in source


def test_rating_flow_is_registered_before_generic_chat_handlers():
    source = read("app/handlers/__init__.py")
    assert "from . import platform_automation_ui" in source
    assert source.index("from . import platform_automation_ui") < source.index("from . import chat")


def test_rating_notification_preserves_anonymity():
    source = read("app/handlers/platform_automation_ui.py")
    assert "Новая оценка диалога" in source
    assert "pending.rater_id" not in source.split("add_notification(", 1)[1]

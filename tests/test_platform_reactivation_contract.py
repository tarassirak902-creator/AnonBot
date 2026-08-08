from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_reactivation_routes_registered_before_legacy_handlers():
    text = (ROOT / "app/handlers/__init__.py").read_text(encoding="utf-8")
    assert "from . import platform_reactivation_ui" in text
    assert text.index("from . import platform_reactivation_ui") < text.index("from . import callbacks_profile")
    assert text.index("from . import platform_reactivation_ui") < text.index("from . import chat")


def test_reactivation_repository_has_atomic_and_unique_guards():
    text = (ROOT / "app/database/platform_reactivation_repository.py").read_text(encoding="utf-8").lower()
    assert "begin immediate" in text
    assert "primary key(user_id, return_day)" in text
    assert "primary key(user_id, week_key)" in text
    assert "insert or ignore into reactivation_rewards" in text
    assert "apply_reward_bundle" in text
    assert "await db.rollback()" in text
    assert "comeback_min_days = 2" in text


def test_reactivation_privacy_contract():
    text = (ROOT / "app/database/platform_reactivation_repository.py").read_text(encoding="utf-8").lower()
    assert "message_text" not in text
    assert "caption" not in text
    assert "message_body" not in text
    assert "payload_text" not in text


def test_growth_hub_exposes_reactivation_for_user_and_admin():
    text = (ROOT / "app/handlers/platform_growth_ui.py").read_text(encoding="utf-8")
    assert 'callback_data="reactivation_center"' in text
    assert 'callback_data="admin_reactivation_metrics"' in text


def test_reactivation_ui_delegates_atomic_reward_to_repository():
    text = (ROOT / "app/handlers/platform_reactivation_ui.py").read_text(encoding="utf-8")
    assert "claim_reactivation_reward" in text
    assert "COMEBACK_REWARD_STARS" in text
    assert "COMEBACK_REWARD_XP" in text
    assert "run_state_action" in text
    assert "grant_xp_once" not in text
    assert "add_user_balance" not in text

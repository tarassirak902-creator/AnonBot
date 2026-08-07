from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_personal_goals_repository_has_atomic_unique_ledger():
    text = (ROOT / "app/database/platform_personal_goals_repository.py").read_text(encoding="utf-8")
    assert "PRIMARY KEY(user_id, day_key, event_key)" in text
    assert "BEGIN IMMEDIATE" in text
    assert "reward_claimed=0" in text
    assert "event_key not in _goal_keys" in text


def test_personal_goal_routes_registered_before_legacy_chat():
    text = (ROOT / "app/handlers/__init__.py").read_text(encoding="utf-8")
    personal = text.index("from . import platform_personal_goals_ui")
    chat = text.index("from . import chat")
    assert personal < chat


def test_growth_center_exposes_personal_plan_and_admin_metrics():
    text = (ROOT / "app/handlers/platform_growth_ui.py").read_text(encoding="utf-8")
    assert 'callback_data="personal_goals"' in text
    assert 'callback_data="admin_personal_goals"' in text
    assert 'record_personal_goal_event(callback.from_user.id, "growth_open")' in text
    assert 'record_personal_goal_event(callback.from_user.id, "daily_claim")' in text


def test_real_feature_routes_record_goal_events():
    shop = (ROOT / "app/handlers/platform_shop_ui.py").read_text(encoding="utf-8")
    referrals = (ROOT / "app/handlers/platform_referral_ui.py").read_text(encoding="utf-8")
    missions = (ROOT / "app/handlers/platform_missions_ui.py").read_text(encoding="utf-8")
    assert 'record_personal_goal_event(callback.from_user.id, "shop_open")' in shop
    assert 'record_personal_goal_event(callback.from_user.id, "referral_open")' in referrals
    assert 'record_personal_goal_event(callback.from_user.id, "missions_open")' in missions


def test_personal_analytics_do_not_store_message_content():
    text = (ROOT / "app/database/platform_personal_goals_repository.py").read_text(encoding="utf-8")
    lowered = text.lower()
    assert "message_text" not in lowered
    assert "caption" not in lowered
    assert "content" not in lowered

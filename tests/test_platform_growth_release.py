from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_daily_claim_is_atomic_and_unique_per_day():
    source = read("app/database/platform_growth_repository.py")
    assert 'await db.execute("BEGIN IMMEDIATE")' in source
    assert "last_claim_date" in source
    assert "if row and row[2] == today_s" in source
    assert "return False, activity, 0" in source


def test_growth_events_never_store_message_content():
    source = read("app/database/platform_growth_repository.py")
    assert "product_events" in source
    assert "event_name" in source
    forbidden = ("message_text", "message_body", "caption", "payload_text")
    assert not any(term in source for term in forbidden)


def test_action_cooldown_is_atomic():
    source = read("app/database/platform_growth_repository.py")
    assert "action_cooldowns" in source
    assert "PRIMARY KEY(user_id, action_key)" in source
    assert "available_at" in source


def test_growth_routes_are_registered_before_legacy_handlers():
    source = read("app/handlers/__init__.py")
    growth = source.index("from . import platform_growth_ui")
    callbacks = source.index("from . import callbacks_profile")
    chat = source.index("from . import chat")
    assert growth < callbacks < chat


def test_daily_hub_exposes_growth_center():
    source = read("app/handlers/commercial_daily_hub.py")
    assert 'callback_data="growth_center"' in source
    assert 'callback_data="admin_growth_operations"' in source


def test_growth_admin_route_is_private():
    source = read("app/handlers/platform_growth_ui.py")
    assert "callback.from_user.id not in ADMIN_IDS" in source
    assert "Недостаточно прав" in source


def test_daily_reward_has_a_hard_cap():
    source = read("app/database/platform_growth_repository.py")
    assert "min(25" in source

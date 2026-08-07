from pathlib import Path


def test_events_and_audit_handlers_are_registered() -> None:
    init_source = Path("app/handlers/__init__.py").read_text(encoding="utf-8")
    assert "from . import events_audit_ui" in init_source

    source = Path("app/handlers/events_audit_ui.py").read_text(encoding="utf-8")
    assert '"weekly_event_hub"' in source
    assert 'weekly_event_claim' in source
    assert 'admin_audit_journal' in source


def test_weekly_reward_is_atomic_and_once_per_week() -> None:
    source = Path("app/handlers/events_audit_ui.py").read_text(encoding="utf-8")
    assert "BEGIN IMMEDIATE" in source
    assert "PRIMARY KEY(user_id, week_key)" in source
    assert "INSERT OR IGNORE INTO weekly_event_claims" in source
    assert "stars_balance=COALESCE(stars_balance,0)+?" in source


def test_visible_entry_buttons_exist() -> None:
    profile = Path("app/handlers/profile_view.py").read_text(encoding="utf-8")
    admin = Path("app/handlers/platform_dashboard_ui.py").read_text(encoding="utf-8")
    assert 'text="🎪 Событие"' in profile
    assert 'callback_data="weekly_event_hub"' in profile
    assert 'text="🧾 Журнал"' in admin
    assert 'audit_callback = "admin_audit_from_ops"' in admin
    assert 'audit_callback = "admin_audit_from_ops_growth"' in admin


def test_privacy_contract_does_not_expose_message_content() -> None:
    source = Path("app/handlers/events_audit_ui.py").read_text(encoding="utf-8")
    assert "Содержимое переписки не анализируется" in source
    assert "Тексты сообщений и переписка не выводятся" in source
    assert "details" not in source
    assert "message.text" not in source

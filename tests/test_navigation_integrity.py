from __future__ import annotations

from pathlib import Path

import pytest

from app.core.navigation import PARENTS, back_button, parent_target, screen_contract


ROOT = Path(__file__).resolve().parents[1]
HANDLERS = ROOT / "app" / "handlers"


def _source(name: str) -> str:
    return (HANDLERS / name).read_text(encoding="utf-8")


def test_navigation_parent_registry_has_unique_callbacks() -> None:
    callbacks = [target.callback_data for target in PARENTS.values()]
    assert len(callbacks) == len(set(callbacks))


def test_unknown_navigation_parent_fails_fast() -> None:
    with pytest.raises(ValueError):
        parent_target("missing-parent")


def test_back_button_uses_registered_parent() -> None:
    button = back_button("activity")
    assert button.callback_data == "profile_hub_activity"
    assert "Активность" in button.text


def test_profile_nested_screens_return_to_immediate_hubs() -> None:
    achievements = _source("profile_achievements.py")
    activity = _source("profile_action_entry.py")
    social = _source("platform_social_ui.py")
    contacts = _source("platform_dashboard_ui.py")

    assert 'callback_data="profile_hub_activity"' in achievements
    assert 'text="⬅️ Награды", callback_data="profile_hub_rewards"' in activity
    assert 'text="⬅️ Социальное", callback_data="profile_hub_social"' in activity
    assert screen_contract("community").parent == "more"
    assert 'screen_back_button("community")' in social
    assert 'callback_data="platform_community_contacts"' in social
    assert 'callback_data="platform_community"' in contacts
    assert 'callback_data="community_connections"' in contacts


def test_weekly_event_preserves_entry_parent() -> None:
    event = _source("events_audit_ui.py")
    alias = _source("commercial_profile_aliases.py")
    shop = _source("platform_shop_ui.py")

    assert 'parent="rewards"' in alias
    assert '"weekly_event:shop"' in shop
    assert '"profile_hub_rewards", "⬅️ Награды"' in event
    assert '"commercial_daily_hub", "⬅️ Мой день"' in event
    assert '"shop_category:seasonal", "⬅️ Сезонное"' in event


def test_growth_admin_links_are_context_aware() -> None:
    growth = _source("platform_growth_ui.py")
    assert 'callback_data="admin_retention_from_growth"' in growth
    assert 'callback_data="admin_business_from_growth"' in growth
    assert 'callback_data="admin_ops_from_growth"' in growth
    assert 'callback_data="admin_platform_health_from_growth"' in growth


def test_operations_context_survives_refresh_and_nested_navigation() -> None:
    ops = _source("platform_dashboard_ui.py")
    retention = _source("engagement_ui.py")
    health = _source("activity_health_ui.py")

    assert 'refresh = "admin_ops_from_growth"' in ops
    assert '"admin_platform_health_from_ops_growth"' in ops
    assert '"admin_retention_from_ops_growth"' in ops
    assert '"admin_audit_from_ops_growth"' in ops
    assert '"admin_ops_from_growth", "⬅️ Операции"' in retention
    assert '"admin_ops_from_growth", "⬅️ Операции"' in health


def test_referral_statistics_preserve_growth_parent() -> None:
    hub = _source("platform_referral_ui.py")
    legacy = _source("referrals.py")
    assert 'callback_data="referral_stats_growth"' in hub
    assert '"referral_stats_growth"' in legacy
    assert '"platform_referrals", "⬅️ Приглашения"' in legacy


def test_context_callbacks_have_registered_handlers() -> None:
    sources = "\n".join(path.read_text(encoding="utf-8") for path in HANDLERS.glob("*.py"))
    context_callbacks = {
        "weekly_event:shop",
        "admin_retention_from_growth",
        "admin_business_from_growth",
        "admin_ops_from_growth",
        "admin_platform_health_from_growth",
        "admin_retention_from_ops_growth",
        "admin_platform_health_from_ops_growth",
        "admin_audit_from_ops_growth",
        "platform_community_contacts",
        "referral_stats_growth",
    }
    for callback in context_callbacks:
        assert sources.count(callback) >= 2, f"Navigation callback has no registered route: {callback}"

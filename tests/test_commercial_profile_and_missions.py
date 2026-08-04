from pathlib import Path


def test_profile_is_grouped_into_commercial_sections() -> None:
    source = Path("app/handlers/profile_view.py").read_text(encoding="utf-8")
    for label in ("⚡ Активность", "🎁 Награды", "🤝 Социальное", "👑 Премиум"):
        assert label in source
    for callback in (
        "profile_hub_activity",
        "profile_hub_rewards",
        "profile_hub_social",
        "profile_hub_premium",
    ):
        assert callback in source


def test_mission_render_and_claim_use_same_service() -> None:
    source = Path("app/handlers/profile_action_entry.py").read_text(encoding="utf-8")
    assert "load_daily_missions" in source
    assert "claim_daily_mission" in source
    assert 'callback_data=f"engagement_mission_claim:{code}"' in source
    assert '("messages",' not in source
    assert '("visit",' not in source


def test_weekly_event_has_commercial_alias() -> None:
    source = Path("app/handlers/commercial_profile_aliases.py").read_text(encoding="utf-8")
    assert 'F.data == "weekly_event"' in source
    assert "_render_event" in source

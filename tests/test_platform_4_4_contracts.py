from pathlib import Path


def test_platform_4_4_missions_registered_before_legacy_callbacks() -> None:
    source = Path("app/handlers/__init__.py").read_text(encoding="utf-8")
    assert source.index("from . import platform_missions_ui") < source.index("from . import callbacks_profile")


def test_growth_center_exposes_missions_and_admin_metrics() -> None:
    source = Path("app/handlers/platform_growth_ui.py").read_text(encoding="utf-8")
    assert 'callback_data="season_missions"' in source
    assert 'callback_data="admin_mission_metrics"' in source


def test_mission_repository_blocks_duplicate_progress_and_rewards() -> None:
    source = Path("app/database/platform_missions_repository.py").read_text(encoding="utf-8")
    assert "UNIQUE(user_id, season_key, event_key)" in source
    assert "BEGIN IMMEDIATE" in source
    assert "reward_claimed=0" in source
    assert "grant_xp_once" in source


def test_mission_analytics_do_not_store_message_content() -> None:
    source = Path("app/database/platform_missions_repository.py").read_text(encoding="utf-8")
    assert "message_text" not in source
    assert "caption" not in source
    assert "event_key" in source

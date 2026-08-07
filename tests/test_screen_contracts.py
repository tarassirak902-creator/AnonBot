from pathlib import Path

from app.core.navigation import PARENTS, SCREENS, screen_contract


ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_screen_contracts_have_valid_parents_and_scopes() -> None:
    assert SCREENS
    callbacks = set()
    for key, contract in SCREENS.items():
        assert contract.key == key
        assert contract.callback_data
        assert contract.refresh_callback
        assert contract.scope in {"user", "admin"}
        assert contract.callback_data not in callbacks
        callbacks.add(contract.callback_data)
        if contract.parent is not None:
            assert contract.parent in PARENTS
            assert contract.back_label


def test_screen_contract_lookup_is_strict() -> None:
    assert screen_contract("growth").refresh_callback == "growth_center"
    assert screen_contract("community").parent == "more"


def test_migrated_hubs_use_contract_buttons() -> None:
    for path in (
        "app/handlers/platform_growth_ui.py",
        "app/handlers/platform_social_ui.py",
        "app/handlers/activity_health_ui.py",
    ):
        source = _source(path)
        assert "screen_refresh_button" in source
        assert "screen_back_button" in source


def test_growth_and_community_do_not_duplicate_contract_routes() -> None:
    growth = _source("app/handlers/platform_growth_ui.py")
    social = _source("app/handlers/platform_social_ui.py")
    assert 'callback_data="growth_center"' not in growth
    assert 'callback_data="commercial_daily_hub"' not in growth
    assert 'callback_data="platform_community"' not in social
    assert 'callback_data="commercial_more_back"' not in social


def test_notification_and_reputation_back_paths_share_community_contract() -> None:
    assert screen_contract("notifications").parent == "community"
    assert screen_contract("reputation").parent == "community"
    social = _source("app/handlers/platform_social_ui.py")
    assert '_back_keyboard("reputation")' in social
    assert 'screen_back_button("notifications")' in social

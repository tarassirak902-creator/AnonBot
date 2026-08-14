from pathlib import Path

from app.handlers import router
from app.handlers import callbacks_profile, chat_actions_ui, dialog_ui, menus, navigation_fallback_ui, profile_games_ui, visible_button_aliases


def _callbacks(observer) -> set[object]:
    return {getattr(handler, "callback", None) for handler in observer.handlers}


def test_legacy_dialog_and_chat_actions_are_physically_removed_from_menus() -> None:
    callbacks = _callbacks(router.message)
    for removed_name in (
        "next_partner",
        "end_dialog",
        "show_gifts",
        "reveal_partner",
        "complaint_menu",
    ):
        assert not hasattr(menus, removed_name)

    for canonical in (
        dialog_ui.next_partner_ui,
        dialog_ui.end_dialog_ui,
        chat_actions_ui.show_gifts,
        chat_actions_ui.reveal_partner,
        chat_actions_ui.complaint_menu,
    ):
        assert canonical in callbacks

    for removed_alias in ("route_chat_gift", "route_reveal", "route_complaint"):
        assert not hasattr(visible_button_aliases, removed_alias)


def test_extracted_profile_and_games_are_physically_removed_from_menus() -> None:
    callbacks = _callbacks(router.message)
    for removed_name in (
        "profile",
        "solo_games_start_menu",
        "duel_games_start_menu",
        "search_casper_game",
    ):
        assert not hasattr(menus, removed_name)
    for canonical in (
        profile_games_ui.profile_entry,
        profile_games_ui.solo_games_entry,
        profile_games_ui.duel_games_entry,
        profile_games_ui.search_casper_game_entry,
    ):
        assert canonical in callbacks
    for removed_alias in ("route_profile", "route_games", "route_duel"):
        assert not hasattr(visible_button_aliases, removed_alias)


def test_duplicate_legacy_main_menu_callback_is_physically_removed() -> None:
    callbacks = _callbacks(router.callback_query)
    assert not hasattr(callbacks_profile, "nav_main_menu_handler")
    assert navigation_fallback_ui.nav_main_menu in callbacks


def test_runtime_pruning_layer_is_fully_retired() -> None:
    source = Path("app/handlers/__init__.py").read_text(encoding="utf-8")
    assert "legacy_runtime_pruning" not in source
    assert "install_legacy_runtime_pruning" not in source
    assert not Path("app/handlers/legacy_runtime_pruning.py").exists()

    assert source.index("from . import chat_actions_ui") < source.index("from . import menus")
    assert source.index("from . import profile_games_ui") < source.index("from . import menus")
    assert "from . import callbacks_profile" in source


def test_compatibility_router_no_longer_owns_canonical_feature_labels() -> None:
    source = Path("app/handlers/visible_button_aliases.py").read_text(encoding="utf-8")
    for name in ("route_chat_gift", "route_reveal", "route_complaint", "route_profile", "route_games", "route_duel"):
        assert f"def {name}" not in source

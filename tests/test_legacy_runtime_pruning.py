from pathlib import Path

from app.handlers import router
from app.handlers import callbacks_profile, chat_actions_ui, dialog_ui, menus, navigation_fallback_ui, profile_games_ui, visible_button_aliases


def _callbacks(observer) -> set[object]:
    return {getattr(handler, "callback", None) for handler in observer.handlers}


def test_legacy_dialog_teardown_handlers_are_not_live() -> None:
    callbacks = _callbacks(router.message)
    assert menus.next_partner not in callbacks
    assert menus.end_dialog not in callbacks
    assert dialog_ui.next_partner_ui in callbacks
    assert dialog_ui.end_dialog_ui in callbacks


def test_extracted_chat_actions_are_canonical_runtime_handlers() -> None:
    callbacks = _callbacks(router.message)
    for legacy in (menus.show_gifts, menus.reveal_partner, menus.complaint_menu):
        assert legacy not in callbacks
    for canonical in (chat_actions_ui.show_gifts, chat_actions_ui.reveal_partner, chat_actions_ui.complaint_menu):
        assert canonical in callbacks
    for removed_alias in ("route_chat_gift", "route_reveal", "route_complaint"):
        assert not hasattr(visible_button_aliases, removed_alias)


def test_extracted_profile_and_games_are_canonical_runtime_handlers() -> None:
    callbacks = _callbacks(router.message)
    for legacy in (menus.profile, menus.solo_games_start_menu, menus.duel_games_start_menu, menus.search_casper_game):
        assert legacy not in callbacks
    for canonical in (
        profile_games_ui.profile_entry,
        profile_games_ui.solo_games_entry,
        profile_games_ui.duel_games_entry,
        profile_games_ui.search_casper_game_entry,
    ):
        assert canonical in callbacks
    for removed_alias in ("route_profile", "route_games", "route_duel"):
        assert not hasattr(visible_button_aliases, removed_alias)


def test_duplicate_legacy_main_menu_callback_is_not_live() -> None:
    callbacks = _callbacks(router.callback_query)
    assert callbacks_profile.nav_main_menu_handler not in callbacks
    assert navigation_fallback_ui.nav_main_menu in callbacks


def test_pruning_runs_after_legacy_modules_load() -> None:
    source = Path("app/handlers/__init__.py").read_text(encoding="utf-8")
    pruning = source.index("install_legacy_runtime_pruning(")
    assert source.index("from . import menus") < pruning
    assert source.index("from . import callbacks_profile") < pruning
    assert source.index("from . import chat_actions_ui") < source.index("from . import menus")
    assert source.index("from . import profile_games_ui") < source.index("from . import menus")


def test_compatibility_router_no_longer_owns_canonical_feature_labels() -> None:
    source = Path("app/handlers/visible_button_aliases.py").read_text(encoding="utf-8")
    for name in ("route_chat_gift", "route_reveal", "route_complaint", "route_profile", "route_games", "route_duel"):
        assert f"def {name}" not in source

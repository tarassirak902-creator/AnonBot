from pathlib import Path

from app.handlers import router
from app.handlers import callbacks_profile, dialog_ui, menus, navigation_fallback_ui


def _callbacks(observer) -> set[object]:
    return {getattr(handler, "callback", None) for handler in observer.handlers}


def test_legacy_dialog_teardown_handlers_are_not_live() -> None:
    callbacks = _callbacks(router.message)
    assert menus.next_partner not in callbacks
    assert menus.end_dialog not in callbacks
    assert dialog_ui.next_partner_ui in callbacks
    assert dialog_ui.end_dialog_ui in callbacks


def test_duplicate_legacy_main_menu_callback_is_not_live() -> None:
    callbacks = _callbacks(router.callback_query)
    assert callbacks_profile.nav_main_menu_handler not in callbacks
    assert navigation_fallback_ui.nav_main_menu in callbacks


def test_pruning_is_installed_after_legacy_modules_load() -> None:
    source = Path("app/handlers/__init__.py").read_text(encoding="utf-8")
    pruning = source.index("install_legacy_runtime_pruning(menus=menus, callbacks_profile=callbacks_profile)")
    assert source.index("from . import menus") < pruning
    assert source.index("from . import callbacks_profile") < pruning

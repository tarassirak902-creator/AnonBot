from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .shared import router


def _callback_of(handler: Any) -> Any:
    return getattr(handler, "callback", None)


def _remove_callbacks(observer: Any, callbacks: Iterable[Any]) -> int:
    blocked = set(callbacks)
    before = len(observer.handlers)
    observer.handlers[:] = [
        handler for handler in observer.handlers
        if _callback_of(handler) not in blocked
    ]
    return before - len(observer.handlers)


def install_legacy_runtime_pruning(*, menus: Any, callbacks_profile: Any) -> dict[str, int]:
    """Remove shadowed legacy routes from the live aiogram registry.

    These functions remain in the large legacy source modules temporarily, but they
    must not be executable at runtime. Canonical equivalents are registered earlier
    in ``dialog_ui`` and ``navigation_fallback_ui``. Keeping this pruning explicit
    makes import-order changes unable to reactivate the old teardown/navigation
    behavior while the source modules are split gradually.
    """
    message_removed = _remove_callbacks(
        router.message,
        (
            menus.next_partner,
            menus.end_dialog,
        ),
    )
    callback_removed = _remove_callbacks(
        router.callback_query,
        (
            callbacks_profile.nav_main_menu_handler,
        ),
    )
    return {
        "message_handlers": message_removed,
        "callback_handlers": callback_removed,
    }

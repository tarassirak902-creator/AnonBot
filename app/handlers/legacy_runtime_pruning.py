from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .shared import router


MESSAGE_LEGACY_NAMES = (
    "next_partner",
    "end_dialog",
    "show_gifts",
    "reveal_partner",
    "complaint_menu",
    "profile",
    "solo_games_start_menu",
    "duel_games_start_menu",
    "search_casper_game",
)
CALLBACK_LEGACY_NAMES = ("nav_main_menu_handler",)


def _callback_of(handler: Any) -> Any:
    return getattr(handler, "callback", None)


def _existing_callbacks(module: Any, names: Iterable[str]) -> tuple[Any, ...]:
    return tuple(callback for name in names if (callback := getattr(module, name, None)) is not None)


def _remove_callbacks(observer: Any, callbacks: Iterable[Any]) -> int:
    blocked = set(callbacks)
    before = len(observer.handlers)
    observer.handlers[:] = [handler for handler in observer.handlers if _callback_of(handler) not in blocked]
    return before - len(observer.handlers)


def install_legacy_runtime_pruning(*, menus: Any, callbacks_profile: Any) -> dict[str, int]:
    return {
        "message_handlers": _remove_callbacks(
            router.message,
            _existing_callbacks(menus, MESSAGE_LEGACY_NAMES),
        ),
        "callback_handlers": _remove_callbacks(
            router.callback_query,
            _existing_callbacks(callbacks_profile, CALLBACK_LEGACY_NAMES),
        ),
    }

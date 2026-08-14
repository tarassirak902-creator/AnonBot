from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .shared import router


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
    # Message-handler migrations are now physical source deletions. Keep the
    # legacy return key for compatibility with startup diagnostics until the
    # remaining callback duplicate is removed as well.
    return {
        "message_handlers": 0,
        "callback_handlers": _remove_callbacks(
            router.callback_query,
            _existing_callbacks(callbacks_profile, CALLBACK_LEGACY_NAMES),
        ),
    }

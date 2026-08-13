from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .shared import router


def _callback_of(handler: Any) -> Any:
    return getattr(handler, "callback", None)


def _remove_callbacks(observer: Any, callbacks: Iterable[Any]) -> int:
    blocked = set(callbacks)
    before = len(observer.handlers)
    observer.handlers[:] = [handler for handler in observer.handlers if _callback_of(handler) not in blocked]
    return before - len(observer.handlers)


def install_legacy_runtime_pruning(*, menus: Any, callbacks_profile: Any, visible_button_aliases: Any | None = None) -> dict[str, int]:
    message_callbacks = [
        menus.next_partner,
        menus.end_dialog,
        menus.show_gifts,
        menus.reveal_partner,
        menus.complaint_menu,
    ]
    if visible_button_aliases is not None:
        message_callbacks += [
            visible_button_aliases.route_chat_gift,
            visible_button_aliases.route_reveal,
            visible_button_aliases.route_complaint,
        ]
    return {
        "message_handlers": _remove_callbacks(router.message, message_callbacks),
        "callback_handlers": _remove_callbacks(router.callback_query, (callbacks_profile.nav_main_menu_handler,)),
    }

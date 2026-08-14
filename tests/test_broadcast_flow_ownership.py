from pathlib import Path

from app.handlers import callbacks_broadcast, menus, router


def _callbacks(observer) -> set[object]:
    return {getattr(handler, "callback", None) for handler in observer.handlers}


def test_broadcast_setup_is_physically_removed_from_menus() -> None:
    for removed_name in (
        "broadcast_start",
        "broadcast_preview_kb",
        "show_broadcast_preview",
        "broadcast_receive_message",
        "broadcast_add_text",
        "broadcast_receive_text",
        "broadcast_back_preview",
        "broadcast_add_button",
        "broadcast_receive_button",
    ):
        assert not hasattr(menus, removed_name)


def test_callbacks_broadcast_owns_complete_broadcast_flow() -> None:
    callbacks = _callbacks(router.message) | _callbacks(router.callback_query)
    for canonical in (
        callbacks_broadcast.broadcast_start,
        callbacks_broadcast.broadcast_receive_message,
        callbacks_broadcast.broadcast_add_text,
        callbacks_broadcast.broadcast_receive_text,
        callbacks_broadcast.broadcast_back_preview,
        callbacks_broadcast.broadcast_add_button,
        callbacks_broadcast.broadcast_receive_button,
        callbacks_broadcast.broadcast_cancel,
        callbacks_broadcast.broadcast_confirm,
    ):
        assert canonical in callbacks


def test_broadcast_module_keeps_confirmation_routes() -> None:
    source = Path("app/handlers/callbacks_broadcast.py").read_text(encoding="utf-8")
    assert 'F.data == "confirm_broadcast"' in source
    assert 'F.data == "cancel_broadcast"' in source

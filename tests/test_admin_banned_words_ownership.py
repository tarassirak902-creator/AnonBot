from pathlib import Path

from app.handlers import admin_banned_words, menus, router


def _callbacks(observer) -> set[object]:
    return {getattr(handler, "callback", None) for handler in observer.handlers}


def test_banned_words_flow_is_physically_removed_from_menus() -> None:
    for removed_name in (
        "banned_words_screen",
        "banned_words",
        "admin_word_add",
        "admin_word_add_receive",
        "admin_words_callbacks",
        "admin_word_delete",
    ):
        assert not hasattr(menus, removed_name)


def test_banned_words_flow_is_registered_from_canonical_module() -> None:
    message_callbacks = _callbacks(router.message)
    callback_callbacks = _callbacks(router.callback_query)

    assert admin_banned_words.banned_words in message_callbacks
    assert admin_banned_words.admin_word_add_receive in message_callbacks
    assert admin_banned_words.admin_word_add in callback_callbacks
    assert admin_banned_words.admin_words_callbacks in callback_callbacks
    assert admin_banned_words.admin_word_delete in callback_callbacks


def test_banned_words_module_loads_before_menus() -> None:
    source = Path("app/handlers/__init__.py").read_text(encoding="utf-8")
    assert source.index("from . import admin_banned_words") < source.index("from . import menus")

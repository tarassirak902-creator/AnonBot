from app.handlers import search_ui


def test_search_copy_uses_visible_states() -> None:
    search_ui.install_search_copy()

    captions = search_ui.shared.SEARCH_CAPTIONS
    assert "<b>🚀 Поиск запущен</b>" in captions["start"]
    assert "<b>⏳ Всё ещё ищем</b>" in captions["waiting"]
    assert "<b>💬 Собеседник найден</b>" in captions["found"]
    assert "<b>⌛ Поиск завершён</b>" in captions["timeout"]
    assert "━━━━━━━━" not in "\n".join(captions.values())


def test_search_handlers_keep_legacy_cancel_label_compatible() -> None:
    source = open("app/handlers/search_ui.py", encoding="utf-8").read()
    assert '"❌  Отменить поиск"' in source
    assert '"❌ Отменить поиск"' in source
    assert '"queue_leave"' in source
    assert '"user_cancelled"' in source


def test_search_ui_is_registered_before_legacy_menus() -> None:
    source = open("app/handlers/__init__.py", encoding="utf-8").read()
    assert source.index("from .search_ui import install_search_copy") < source.index("from . import menus")
    assert source.index("install_search_copy()") < source.index("from . import menus")

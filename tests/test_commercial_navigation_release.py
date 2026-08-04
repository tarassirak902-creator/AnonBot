from pathlib import Path


def test_main_keyboard_is_grouped_for_commercial_navigation() -> None:
    source = Path("app/handlers/minimal_keyboard_ui.py").read_text(encoding="utf-8")
    assert '"more": "✨ Ещё"' in source
    assert 'input_field_placeholder="Выберите раздел"' in source
    assert 'KeyboardButton(text=MAIN_LABELS["chat"])' in source
    assert 'KeyboardButton(text=MAIN_LABELS["profile"])' in source
    assert 'MAIN_LABELS["admin"] if is_admin else MAIN_LABELS["more"]' in source


def test_more_hub_keeps_service_and_commercial_entries() -> None:
    source = Path("app/handlers/commercial_navigation_ui.py").read_text(encoding="utf-8")
    assert 'F.text == "✨ Ещё"' in source
    assert "📢 Новости" in source
    assert "🛟 Поддержка" in source
    assert "📣 Реклама" in source
    assert "🔐 Приватность" in source
    assert 'F.data == "commercial_ads_info"' in source


def test_admin_hub_is_task_oriented() -> None:
    source = Path("app/handlers/commercial_navigation_ui.py").read_text(encoding="utf-8")
    for label in ("📡 Операции", "📈 Аналитика", "🩺 Система", "🚨 Модерация", "📨 Коммуникации"):
        assert label in source
    assert 'F.text.in_({"⚙️ Админка", "⚙️ Управление"})' in source
    assert "ADMIN_IDS" in source


def test_commercial_navigation_is_registered_early() -> None:
    source = Path("app/handlers/__init__.py").read_text(encoding="utf-8")
    assert "from . import commercial_navigation_ui" in source
    assert source.index("from . import commercial_navigation_ui") < source.index("from . import menus")

from pathlib import Path


def test_daily_hub_is_registered_before_legacy_handlers() -> None:
    source = Path("app/handlers/__init__.py").read_text(encoding="utf-8")
    assert "from . import commercial_daily_hub" in source
    assert source.index("from . import commercial_daily_hub") < source.index("from . import menus")


def test_main_menu_exposes_daily_overview() -> None:
    source = Path("app/handlers/minimal_keyboard_ui.py").read_text(encoding="utf-8")
    assert '"daily": "☀️ Мой день"' in source
    assert 'KeyboardButton(text=MAIN_LABELS["daily"])' in source
    assert 'input_field_placeholder="Выберите раздел"' in source


def test_user_daily_hub_uses_existing_services() -> None:
    source = Path("app/handlers/commercial_daily_hub.py").read_text(encoding="utf-8")
    assert "load_daily_missions" in source
    assert "get_user_balance" in source
    assert "is_user_vip" in source
    assert 'F.data == "commercial_daily_hub"' in source
    assert 'F.text == "☀️ Мой день"' in source


def test_admin_hub_exposes_platform_pulse() -> None:
    navigation = Path("app/handlers/commercial_navigation_ui.py").read_text(encoding="utf-8")
    pulse = Path("app/handlers/commercial_daily_hub.py").read_text(encoding="utf-8")
    assert 'text="⚡ Пульс"' in navigation
    assert 'callback_data="admin_platform_pulse"' in navigation
    assert 'F.data == "admin_platform_pulse"' in pulse
    assert "admin_platform_health" in pulse
    assert "admin_complaints_dashboard" in pulse

from pathlib import Path


SOURCE = Path("app/handlers/navigation_fallback_ui.py").read_text(encoding="utf-8")
INIT = Path("app/handlers/__init__.py").read_text(encoding="utf-8")


def test_global_main_menu_fallback_is_registered() -> None:
    assert 'F.data == "nav_main_menu"' in SOURCE
    assert "await state.clear()" in SOURCE
    assert "reply_markup=main_menu(" in SOURCE


def test_profile_fallback_supports_nested_hubs() -> None:
    assert '"nav_profile_home"' in SOURCE
    assert '"profile_hub_back"' in SOURCE
    assert "send_profile_screen" in SOURCE


def test_navigation_fallback_loads_before_legacy_callbacks() -> None:
    assert INIT.index("from . import navigation_fallback_ui") < INIT.index("from . import callbacks_profile")

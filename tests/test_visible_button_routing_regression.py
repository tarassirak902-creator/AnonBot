from pathlib import Path


MENUS = Path("app/handlers/menus.py").read_text(encoding="utf-8")
ALIASES = Path("app/handlers/visible_button_aliases.py").read_text(encoding="utf-8")
INIT = Path("app/handlers/__init__.py").read_text(encoding="utf-8")


def test_full_menu_handler_module_is_present() -> None:
    required_handlers = (
        "async def admin_stats",
        "async def broadcast_start",
        "async def banned_words",
        "async def gifts_management",
        "async def admin_settings",
        "async def admin_logs",
    )
    for handler in required_handlers:
        assert handler in MENUS


def test_redesigned_buttons_have_explicit_routes() -> None:
    for label in (
        "🚀 Начать общение",
        "🎮 Игры",
        "👤 Профиль",
        "🎮 Дуэль",
        "🎁 Подарок",
        "👤 Кто это?",
        "🚨 Жалоба",
    ):
        assert label in ALIASES


def test_aliases_are_registered_after_restored_menus() -> None:
    assert INIT.index("from . import menus") < INIT.index("from . import visible_button_aliases")

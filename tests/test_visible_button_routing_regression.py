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
        "async def admin_withdraw_requests",
    )
    for handler in required_handlers:
        assert handler in MENUS


def test_every_redesigned_primary_button_has_explicit_route() -> None:
    for label in (
        "🚀 Начать общение",
        "❓ Анонимные вопросы",
        "🎮 Игры",
        "👤 Профиль",
        "🎁 Пригласить друга",
        "📣 Разместить рекламу",
        "⚙️ Панель управления",
    ):
        assert f'F.text == "{label}"' in ALIASES


def test_every_redesigned_dialog_button_has_explicit_route() -> None:
    for label in (
        "🎮 Дуэль",
        "🎁 Подарок",
        "👤 Кто это?",
        "🚨 Жалоба",
    ):
        assert f'F.text == "{label}"' in ALIASES


def test_aliases_are_registered_after_all_target_modules() -> None:
    alias_index = INIT.index("from . import visible_button_aliases")
    for dependency in (
        "from . import commands",
        "from . import admin_overview_ui",
        "from . import menus",
        "from . import advertising",
    ):
        assert INIT.index(dependency) < alias_index

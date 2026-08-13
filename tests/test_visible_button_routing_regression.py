from pathlib import Path

from app.handlers.minimal_keyboard_ui import CHAT_LABELS, MAIN_LABELS

HANDLERS = Path("app/handlers")
MENUS = (HANDLERS / "menus.py").read_text(encoding="utf-8")
ALIASES = (HANDLERS / "visible_button_aliases.py").read_text(encoding="utf-8")
ROUTES = "\n".join(path.read_text(encoding="utf-8") for path in HANDLERS.glob("*.py"))
INIT = (HANDLERS / "__init__.py").read_text(encoding="utf-8")


def test_full_menu_handler_module_is_present() -> None:
    for handler in (
        "async def admin_stats", "async def broadcast_start", "async def banned_words",
        "async def gifts_management", "async def admin_withdraw_requests",
    ):
        assert handler in MENUS


def test_every_primary_button_has_explicit_route() -> None:
    for label in MAIN_LABELS.values():
        assert f'"{label}"' in ROUTES


def test_every_dialog_button_has_explicit_route() -> None:
    for label in CHAT_LABELS.values():
        assert f'"{label}"' in ROUTES


def test_legacy_routes_remain_supported() -> None:
    for label in (
        "🚀 Начать общение", "❓ Анонимные вопросы", "🎁 Пригласить друга",
        "📣 Разместить рекламу", "⚙️ Панель управления", "➡️ Новый собеседник",
        "❌ Завершить диалог", "👤 Кто это?",
    ):
        assert f'"{label}"' in ROUTES


def test_alias_dialog_routes_are_alias_only() -> None:
    assert '"➡️ Новый"' in ALIASES
    for label in ("➡️ Новый собеседник", "➡️ Следующий собеседник", "⏹ Завершить", "❌ Завершить диалог"):
        assert f'"{label}"' not in ALIASES


def test_aliases_are_registered_after_all_target_modules() -> None:
    alias_index = INIT.index("from . import visible_button_aliases")
    for dependency in (
        "from . import commands", "from . import admin_overview_ui",
        "from . import menus", "from . import advertising",
    ):
        assert INIT.index(dependency) < alias_index

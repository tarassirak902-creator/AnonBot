from pathlib import Path

from app.handlers.minimal_keyboard_ui import CHAT_LABELS, MAIN_LABELS

HANDLERS = Path("app/handlers")
MENUS = (HANDLERS / "menus.py").read_text(encoding="utf-8")
BROADCAST = (HANDLERS / "callbacks_broadcast.py").read_text(encoding="utf-8")
BANNED_WORDS = (HANDLERS / "admin_banned_words.py").read_text(encoding="utf-8")
ADMIN_GIFTS = (HANDLERS / "admin_gifts.py").read_text(encoding="utf-8")
ADMIN_USERS = (HANDLERS / "admin_users.py").read_text(encoding="utf-8")
ALIASES = (HANDLERS / "visible_button_aliases.py").read_text(encoding="utf-8")
ROUTES = "\n".join(path.read_text(encoding="utf-8") for path in HANDLERS.glob("*.py"))
INIT = (HANDLERS / "__init__.py").read_text(encoding="utf-8")


def test_full_menu_handler_module_is_present() -> None:
    assert "async def admin_stats" in ADMIN_USERS
    assert "async def admin_stats" not in MENUS
    assert "async def admin_withdraw_requests" in MENUS
    assert "async def broadcast_start" in BROADCAST
    assert "async def broadcast_start" not in MENUS
    assert "async def banned_words" in BANNED_WORDS
    assert "async def banned_words" not in MENUS
    assert "async def gifts_management" in ADMIN_GIFTS
    assert "async def gifts_management" not in MENUS


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

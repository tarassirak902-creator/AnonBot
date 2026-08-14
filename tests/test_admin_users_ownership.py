from pathlib import Path

HANDLERS = Path("app/handlers")
MENUS = (HANDLERS / "menus.py").read_text(encoding="utf-8")
USERS = (HANDLERS / "admin_users.py").read_text(encoding="utf-8")
INIT = (HANDLERS / "__init__.py").read_text(encoding="utf-8")


def test_admin_user_flow_has_single_owner() -> None:
    handlers = (
        "def admin_users_menu_kb():",
        "async def admin_stats(",
        "async def search_user(",
        "async def admin_open_stats_callback(",
    )
    for handler in handlers:
        assert handler in USERS
        assert handler not in MENUS


def test_admin_user_routes_and_fsm_are_canonical() -> None:
    for marker in (
        'F.text.in_({"📊 Статистика", "📊 Статистика и пользователи", "👥 Пользователи"})',
        "UserSearch.waiting_for_query",
        'F.data == "admin_open_stats"',
        'callback_data="admin_user_search"',
        'callback_data="admin_warned_list"',
        'callback_data="admin_restricted_list"',
        'callback_data="admin_download_users"',
    ):
        assert marker in USERS


def test_admin_users_register_before_menus() -> None:
    assert INIT.index("from . import admin_users") < INIT.index("from . import menus")


def test_unrelated_admin_flows_stay_in_menus() -> None:
    for handler in (
        "async def admin_withdraw_requests(",
        "async def settings_menu(",
        "async def view_logs(",
        "async def admin_open_broadcast_callback(",
        "async def admin_open_settings_callback(",
        "async def admin_open_logs_callback(",
        "async def admin_open_withdraw_callback(",
    ):
        assert handler in MENUS

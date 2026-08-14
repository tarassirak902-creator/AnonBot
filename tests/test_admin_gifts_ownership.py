from pathlib import Path

HANDLERS = Path("app/handlers")
MENUS = (HANDLERS / "menus.py").read_text(encoding="utf-8")
GIFTS = (HANDLERS / "admin_gifts.py").read_text(encoding="utf-8")
INIT = (HANDLERS / "__init__.py").read_text(encoding="utf-8")


def test_admin_gift_flow_has_single_owner() -> None:
    handlers = (
        "async def gifts_admin_screen(",
        "async def gifts_management(",
        "async def admin_gift_add(",
        "async def admin_gift_add_receive(",
        "async def gift_delete_keyboard(",
        "async def admin_gift_delete_menu(",
        "async def admin_gift_toggle(",
        "async def admin_gift_delete_confirm(",
        "async def admin_gifts_menu_callback(",
    )
    for handler in handlers:
        assert handler in GIFTS
        assert handler not in MENUS


def test_admin_gift_callbacks_and_fsm_are_canonical() -> None:
    for marker in (
        'F.text == "🎁 Управление подарками"',
        'F.data == "admin_gift_add"',
        "GiftAdd.waiting_for_name",
        'F.data == "admin_gift_delete_menu"',
        'F.data.startswith("admin_gift_toggle_")',
        'F.data == "admin_gift_delete_confirm"',
        'F.data == "admin_gifts_menu"',
        "GiftDeleteSelect.selecting",
    ):
        assert marker in GIFTS


def test_admin_gifts_register_before_menus() -> None:
    assert INIT.index("from . import admin_gifts") < INIT.index("from . import menus")

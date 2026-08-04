from app.core.keyboards import (
    admin_panel,
    main_menu,
    question_target_inline,
    questions_home_inline,
    telegram_service_menu_kb,
)
from app.core.ui_copy import metric, screen, section


def test_screen_copy_is_consistent_and_escaped() -> None:
    text = screen(
        "Профиль <CASPER>",
        intro="Привет & добро пожаловать",
        sections=(section("Статус", (metric("⭐", "Баланс", "10 < 20"),)),),
        footer="Выберите действие.",
    )
    assert text.startswith("<b>Профиль &lt;CASPER&gt;</b>")
    assert "Привет &amp; добро пожаловать" in text
    assert "10 &lt; 20" in text
    assert text.endswith("<i>Выберите действие.</i>")


def _assert_compact(markup) -> None:
    rows = getattr(markup, "inline_keyboard", None) or getattr(markup, "keyboard", None)
    assert rows
    assert all(1 <= len(row) <= 2 for row in rows)


def test_core_navigation_keyboards_are_compact() -> None:
    for markup in (
        main_menu(False),
        main_menu(True),
        admin_panel(),
        telegram_service_menu_kb(),
        question_target_inline(),
        questions_home_inline(),
    ):
        _assert_compact(markup)


def test_callback_contracts_are_preserved() -> None:
    target_callbacks = {
        button.callback_data
        for row in question_target_inline().inline_keyboard
        for button in row
    }
    assert target_callbacks == {
        "questions:ask_target",
        "questions:target_gift",
        "nav_main_menu",
    }

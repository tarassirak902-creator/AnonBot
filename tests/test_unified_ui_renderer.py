from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_renderer_treats_not_modified_as_success() -> None:
    source = _source("app/core/ui_renderer.py")
    assert '"message is not modified"' in source
    assert "is_message_not_modified(exc)" in source
    assert "return None" in source


def test_renderer_only_falls_back_when_edit_is_unavailable() -> None:
    source = _source("app/core/ui_renderer.py")
    assert "is_edit_unavailable(exc)" in source
    assert "if not is_edit_unavailable(exc):" in source
    assert "raise" in source
    assert "return await message.answer(text, **kwargs)" in source


def test_growth_shop_and_referrals_use_single_renderer() -> None:
    for path in (
        "app/handlers/platform_growth_ui.py",
        "app/handlers/platform_shop_ui.py",
        "app/handlers/platform_referral_ui.py",
    ):
        source = _source(path)
        assert "from app.core.ui_renderer import render_message" in source
        assert "await render_message(" in source
        assert "callback.message.answer(text" not in source


def test_notifications_read_does_not_answer_callback_twice() -> None:
    source = _source("app/handlers/platform_social_ui.py")
    handler = source.split("async def notifications_read_callback", 1)[1]
    assert "await notifications_callback(callback)" not in handler
    assert "run_state_action(" in handler
    assert "callback.answer(" not in handler
    assert "await _notifications_screen(" in handler
    assert "await render_message(" in handler


def test_community_message_can_send_while_callbacks_edit() -> None:
    source = _source("app/handlers/platform_social_ui.py")
    assert "prefer_edit=edit" in source
    assert "await _render_community(message, message.from_user.id)" in source
    assert "await _render_community(callback.message, callback.from_user.id, edit=True)" in source

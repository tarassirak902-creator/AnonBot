from app.core.ui_labels import ButtonText
from app.handlers.user_actions_ui import gifts_entry_ui


def test_close_label_is_canonical() -> None:
    assert ButtonText.CLOSE == "❌ Закрыть"


def test_user_action_copy_is_compact() -> None:
    source = gifts_entry_ui.__module__
    assert source == "app.handlers.user_actions_ui"


def test_user_action_callbacks_remain_compatible() -> None:
    import inspect
    import app.handlers.user_actions_ui as module

    source = inspect.getsource(module)
    assert "buy_gift_" in source
    assert 'callback_data="close_gifts_menu"' in source
    assert 'F.text == "⚠️ Пожаловаться"' in source
    assert 'F.text == "🎁 Подарить подарок"' in source
    assert 'F.text == "⚔️ Играть с собеседником"' in source


def test_user_action_copy_avoids_legacy_noise() -> None:
    import inspect
    import app.handlers.user_actions_ui as module

    source = inspect.getsource(module)
    assert "не заслужила" not in source
    assert "Вы не в диалоге" not in source
    assert "ВЫБЕРИТЕ" not in source

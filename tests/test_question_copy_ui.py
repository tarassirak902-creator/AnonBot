from app.core.ui_labels import ButtonText
from app.handlers.question_copy_ui import show_question_gifts


def test_question_copy_uses_canonical_navigation() -> None:
    source = __import__("inspect").getsource(show_question_gifts)
    assert "ButtonText.CLOSE" in source
    assert 'callback_data="qgift:close"' in source
    assert "не заслужила" not in source


def test_question_copy_preserves_purchase_callback_contract() -> None:
    source = __import__("inspect").getsource(show_question_gifts)
    assert 'callback_data=f"qgift:{context}:{reference}:{gift_id}"' in source


def test_question_copy_is_installed_before_legacy_handlers() -> None:
    from pathlib import Path

    source = Path("app/handlers/__init__.py").read_text(encoding="utf-8")
    install_at = source.index("install_question_copy_ui()")
    menus_at = source.index("from . import menus")
    assert install_at < menus_at


def test_close_label_is_compact() -> None:
    assert ButtonText.CLOSE == "❌ Закрыть"

from pathlib import Path


def test_question_details_ui_is_installed() -> None:
    source = Path("app/handlers/__init__.py").read_text(encoding="utf-8")
    assert "install_question_details_ui" in source
    assert source.index("install_question_details_ui()") < source.index("from . import commands")


def test_question_details_preserve_reveal_payment_contract() -> None:
    source = Path("app/handlers/question_details_ui.py").read_text(encoding="utf-8")
    assert 'payload=f"question_reveal:{public_id}"' in source
    assert 'amount=100' in source
    assert 'callback_data=f"question_reveal_cancel:{public_id}"' in source
    assert "ButtonText.CANCEL" in source


def test_question_detail_handlers_are_replaced() -> None:
    source = Path("app/handlers/question_details_ui.py").read_text(encoding="utf-8")
    for handler_name in (
        "question_view",
        "question_answer_view",
        "buy_question_author_reveal",
        "cancel_question_author_reveal",
    ):
        assert handler_name in source


def test_question_details_escape_user_content() -> None:
    source = Path("app/handlers/question_details_ui.py").read_text(encoding="utf-8")
    assert "escape(text)" in source
    assert "escape(answer)" in source
    assert "escape(question_text)" in source
    assert "escape(answer_text)" in source
    assert "escape(full_name)" in source
    assert "escape(username)" in source

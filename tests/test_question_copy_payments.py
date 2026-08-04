from app.core.ui_labels import ButtonText
from app.handlers import question_copy_ui


def _texts(markup):
    return [button.text for row in markup.inline_keyboard for button in row]


def _callbacks(markup):
    return [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    ]


def test_question_link_navigation_uses_canonical_back() -> None:
    markup = question_copy_ui.question_link_inline()
    assert ButtonText.BACK in _texts(markup)
    assert _callbacks(markup) == ["questions:profile_help", "questions:home"]


def test_stars_amount_menu_keeps_payment_callbacks() -> None:
    markup = question_copy_ui.stars_amount_inline("q", "public-id")
    callbacks = _callbacks(markup)
    assert "qstars:q:public-id:50" in callbacks
    assert "qstars:q:public-id:500" in callbacks
    assert "qstars_custom:q:public-id" in callbacks
    assert "qstars_close" in callbacks
    assert ButtonText.CANCEL in _texts(markup)


def test_premium_menu_is_compact_and_contract_safe() -> None:
    markup = question_copy_ui.premium_inline("a", "answer-id")
    callbacks = _callbacks(markup)
    assert callbacks == [
        "qpremium:a:answer-id:3:1000",
        "qpremium:a:answer-id:6:1500",
        "qpremium:a:answer-id:12:2500",
        "qpremium_close",
    ]
    assert all(len(row) <= 2 for row in markup.inline_keyboard)
    assert ButtonText.CANCEL in _texts(markup)


def test_install_replaces_question_presentation_boundaries() -> None:
    question_copy_ui.install_question_copy_ui()
    questions = question_copy_ui.questions
    assert questions._send_question_stars_invoice is question_copy_ui.send_question_stars_invoice
    assert questions._send_question_premium_invoice is question_copy_ui.send_question_premium_invoice
    assert questions._return_from_gift_menu is question_copy_ui.return_from_gift_menu
    assert questions.question_link_inline is question_copy_ui.question_link_inline

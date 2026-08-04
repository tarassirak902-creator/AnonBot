from app.handlers.question_browser_ui import (
    answer_card_inline,
    answers_page_inline,
    premium_inline,
    question_card_inline,
    question_link_inline,
    questions_page_inline,
    stars_amount_inline,
)


def _buttons(markup):
    return [button for row in markup.inline_keyboard for button in row]


def test_question_lists_keep_existing_callback_contracts() -> None:
    question_rows = [(7, "q-public", "new", "2026-08-05T10:00:00")]
    answer_rows = [(7, "q-public", "2026-08-05T11:00:00", None)]

    question_buttons = _buttons(questions_page_inline(question_rows, True, True, 5))
    answer_buttons = _buttons(answers_page_inline(answer_rows, True, True, 5))

    assert {button.callback_data for button in question_buttons} >= {
        "questions:view:q-public",
        "questions:page:0",
        "questions:page:10",
        "questions:home",
    }
    assert {button.callback_data for button in answer_buttons} >= {
        "questions:answer_view:q-public",
        "questions:answers_page:0",
        "questions:answers_page:10",
        "questions:home",
    }


def test_question_cards_are_compact_and_keep_actions() -> None:
    question_buttons = _buttons(question_card_inline(author_revealed=False))
    answer_buttons = _buttons(answer_card_inline())

    assert max(len(row) for row in question_card_inline().inline_keyboard) <= 2
    assert max(len(row) for row in answer_card_inline().inline_keyboard) <= 2
    assert {button.callback_data for button in question_buttons} == {
        "questions:reply",
        "questions:gift",
        "questions:buy_reveal",
        "questions:back_mine",
    }
    assert {button.callback_data for button in answer_buttons} == {
        "questions:ask_again",
        "questions:answer_gift",
        "questions:back_answers",
    }


def test_payment_navigation_uses_canonical_cancel_label() -> None:
    stars = _buttons(stars_amount_inline("q", "ref"))
    premium = _buttons(premium_inline("a", "ref"))

    assert stars[-1].text == "❌ Отмена"
    assert stars[-1].callback_data == "qstars_close"
    assert premium[-1].text == "❌ Отмена"
    assert premium[-1].callback_data == "qpremium_close"


def test_link_navigation_uses_canonical_back_label() -> None:
    buttons = _buttons(question_link_inline())
    assert buttons[-1].text == "⬅️ Назад"
    assert buttons[-1].callback_data == "questions:home"

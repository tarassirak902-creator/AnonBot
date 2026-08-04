from app.services.deep_link_context import PendingQuestionDeepLinks, parse_question_deep_link


def test_parse_question_deep_link() -> None:
    assert parse_question_deep_link('/start ask_token-123') == 'token-123'
    assert parse_question_deep_link('/start ref_abc') is None
    assert parse_question_deep_link('/start ask_') is None


def test_pending_question_deep_link_is_consumed_once() -> None:
    store = PendingQuestionDeepLinks()
    store.put(42, 'abc')
    assert store.pop(42) == 'abc'
    assert store.pop(42) is None

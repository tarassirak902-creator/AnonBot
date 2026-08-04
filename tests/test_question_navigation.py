from app.services.question_navigation import QuestionNavigation


def test_navigation_builds_page_and_detects_next():
    nav = QuestionNavigation(page_size=2)
    page = nav.build_page([1, 2, 3], offset=0)
    assert page.items == (1, 2)
    assert page.offset == 0
    assert page.has_previous is False
    assert page.has_next is True


def test_navigation_normalizes_offsets():
    nav = QuestionNavigation(page_size=5)
    assert nav.normalize_offset(-10) == 0
    assert nav.previous_offset(3) == 0
    assert nav.previous_offset(10) == 5
    assert nav.next_offset(-1) == 5


def test_navigation_rejects_invalid_page_size():
    try:
        QuestionNavigation(page_size=0)
    except ValueError as exc:
        assert "page_size" in str(exc)
    else:
        raise AssertionError("ValueError was not raised")

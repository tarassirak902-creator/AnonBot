from app.services.question_presentation import (
    build_answer_list_items,
    build_question_list_items,
    display_owner_name,
    format_question_timestamp,
)


def test_display_owner_name_prefers_first_name_then_username():
    assert display_owner_name((1, "ghost", "Casper")) == "Casper"
    assert display_owner_name((1, "ghost", "")) == "@ghost"
    assert display_owner_name((1, "", "")) == "пользователю"
    assert display_owner_name(None) == "пользователю"


def test_format_question_timestamp_handles_iso_and_legacy_values():
    assert format_question_timestamp("2026-08-04T16:05:06") == "04.08.2026 • 16:05"
    assert format_question_timestamp("legacy") == "legacy"
    assert format_question_timestamp(None) == "—"


def test_build_question_list_items_preserves_callbacks_and_status_icons():
    items = build_question_list_items(
        [
            (7, "q-new", "new", "2026-08-04T16:05:06"),
            (8, "q-done", "answered", "legacy"),
            (9, "q-other", "archived", None),
        ]
    )

    assert [item.callback_data for item in items] == [
        "questions:view:q-new",
        "questions:view:q-done",
        "questions:view:q-other",
    ]
    assert items[0].text.startswith("🆕 Вопрос №7")
    assert items[1].text == "✅ Вопрос №8 — legacy"
    assert items[2].text == "❓ Вопрос №9 — —"


def test_build_answer_list_items_marks_unread_and_read_answers():
    items = build_answer_list_items(
        [
            (10, "a-new", "2026-08-04T16:05:06", None),
            (11, "a-read", "legacy", "2026-08-04T17:00:00"),
        ]
    )

    assert items[0].text.startswith("🆕 Ответ на вопрос №10")
    assert items[0].callback_data == "questions:answer_view:a-new"
    assert items[1].text == "💬 Ответ на вопрос №11 — legacy"

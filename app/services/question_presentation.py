from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence


@dataclass(frozen=True, slots=True)
class QuestionListItem:
    text: str
    callback_data: str


def display_owner_name(owner: Sequence[object] | None) -> str:
    """Return the public display name used by the anonymous-question flow."""
    if not owner:
        return "пользователю"
    first_name = str(owner[2] or "").strip() if len(owner) > 2 else ""
    username = str(owner[1] or "").strip() if len(owner) > 1 else ""
    return first_name or (f"@{username}" if username else "пользователю")


def format_question_timestamp(value: object, *, empty: str = "—") -> str:
    raw = str(value or "").strip()
    if not raw:
        return empty
    try:
        return datetime.fromisoformat(raw).strftime("%d.%m.%Y • %H:%M")
    except (TypeError, ValueError):
        return raw


def build_question_list_items(rows: Sequence[Sequence[object]]) -> list[QuestionListItem]:
    items: list[QuestionListItem] = []
    for row in rows:
        if len(row) < 4:
            continue
        question_id, public_id, status, created_at = row[:4]
        icon = "🆕" if status == "new" else ("✅" if status == "answered" else "❓")
        items.append(
            QuestionListItem(
                text=f"{icon} Вопрос №{question_id} — {format_question_timestamp(created_at)}",
                callback_data=f"questions:view:{public_id}",
            )
        )
    return items


def build_answer_list_items(rows: Sequence[Sequence[object]]) -> list[QuestionListItem]:
    items: list[QuestionListItem] = []
    for row in rows:
        if len(row) < 4:
            continue
        question_id, public_id, answered_at, answer_read_at = row[:4]
        icon = "🆕" if not answer_read_at else "💬"
        items.append(
            QuestionListItem(
                text=f"{icon} Ответ на вопрос №{question_id} — {format_question_timestamp(answered_at)}",
                callback_data=f"questions:answer_view:{public_id}",
            )
        )
    return items

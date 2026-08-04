from __future__ import annotations

from html import escape

from aiogram.types import Message

from . import questions


async def show_inline_question_entry(message: Message, token: str, owner) -> None:
    """Show a personal-question entry as an inline card, never a reply keyboard."""
    display_name = questions._display_name(owner)
    await questions.hide_reply_keyboard(message)
    await questions._send_question_flow_card(
        message,
        "actions",
        (
            "❓ <b>Анонимные вопросы</b>\n\n"
            f"Вы перешли по персональной ссылке пользователя <b>{escape(display_name)}</b>.\n\n"
            "Выберите действие ниже. Ваше имя останется скрытым."
        ),
        questions._target_inline(token, display_name),
    )


def install_question_entry_ui() -> None:
    questions.show_question_entry_after_start = show_inline_question_entry

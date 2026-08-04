from __future__ import annotations

from html import escape

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from . import questions


def _entry_keyboard(token: str, display_name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"❓ Задать анонимный вопрос {display_name}",
            callback_data=f"qtarget:{token}",
        )],
        [InlineKeyboardButton(
            text="🏠 Вернуться в главное меню",
            callback_data="question_entry:main_menu",
        )],
    ])


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
        _entry_keyboard(token, display_name),
    )


@questions.router.callback_query(F.data == "question_entry:main_menu")
async def leave_question_entry(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel the deep-link flow and restore the regular main menu."""
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass

    is_admin = callback.from_user.id in questions.ADMIN_IDS
    await questions.send_brand_card(
        callback.message,
        "main_menu",
        "👻 <b>Главное меню CASPER</b>\n\nВыберите нужный раздел ниже.",
        questions.main_menu(is_admin),
    )
    await callback.answer()


def install_question_entry_ui() -> None:
    questions.show_question_entry_after_start = show_inline_question_entry

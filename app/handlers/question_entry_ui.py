from __future__ import annotations

from html import escape

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.core.keyboards import main_menu

from . import questions
from .shared import ADMIN_IDS, router, send_brand_card


def _question_entry_inline(token: str, display_name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"❓ Задать анонимный вопрос {display_name}",
                    callback_data=f"qtarget:{token}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏠 Вернуться в главное меню",
                    callback_data="question_entry:main_menu",
                )
            ],
        ]
    )


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
        _question_entry_inline(token, display_name),
    )


@router.callback_query(F.data == "question_entry:main_menu")
async def close_question_entry(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    questions._question_start_targets.pop(callback.from_user.id, None)
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()
    await send_brand_card(
        callback.message,
        "main_menu",
        "👻 <b>Главное меню CASPER</b>\n\nВыберите нужный раздел ниже.",
        main_menu(callback.from_user.id in ADMIN_IDS),
    )


def install_question_entry_ui() -> None:
    questions.show_question_entry_after_start = show_inline_question_entry

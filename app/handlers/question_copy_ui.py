from __future__ import annotations

from html import escape

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.core.ui_copy import screen
from app.core.ui_labels import ButtonText, ScreenTitle

from . import questions


async def send_target_screen(message: Message, state) -> None:
    await questions._clear_question_screen(message, state)
    data = await state.get_data()
    name = data.get("question_target_name", "пользователю")
    await state.set_state(questions.AnonymousQuestionFlow.target_menu)
    sent = await questions._send_question_flow_card(
        message,
        "actions",
        screen(
            ScreenTitle.QUESTIONS,
            intro=f"Получатель: <b>{escape(name)}</b>",
            footer="Выберите действие. Отправитель останется анонимным.",
        ),
        questions.question_target_inline(name),
    )
    await questions._remember_question_screen(state, sent)


async def send_gift_screen(message: Message, state) -> None:
    await questions._clear_question_screen(message, state)
    await state.set_state(questions.AnonymousQuestionFlow.gift_menu)
    sent = await questions._send_question_flow_card(
        message,
        "gifts",
        screen(
            "🎁 Анонимный подарок",
            intro="Выберите подарок или другую анонимную услугу.",
        ),
        questions.question_gift_inline(),
    )
    await questions._remember_question_screen(state, sent)


async def send_write_question_screen(message: Message, state) -> None:
    await questions._clear_question_screen(message, state)
    data = await state.get_data()
    name = data.get("question_target_name", "пользователю")
    await state.set_state(questions.AnonymousQuestionFlow.waiting_for_question)
    sent = await questions._send_question_flow_card(
        message,
        "write",
        screen(
            "✍️ Новый вопрос",
            intro=f"Получатель: <b>{escape(name)}</b>",
            footer="Отправьте одно текстовое сообщение. Ваше имя не будет показано.",
        ),
        InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=ButtonText.BACK, callback_data="questions:target_home")
        ]]),
    )
    await questions._remember_question_screen(state, sent)


async def show_question_gifts(
    message: Message,
    *,
    context: str,
    reference: str,
) -> None:
    gifts = await questions.db.get_all_gifts()
    if not gifts:
        await message.answer(
            screen("🎁 Подарки", intro="Сейчас нет доступных подарков."),
            parse_mode="HTML",
        )
        return

    is_vip = await questions.db.is_user_vip(message.from_user.id)
    keyboard: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for gift_id, name, emoji, price in gifts:
        actual_price = int(price * 0.7) if is_vip else int(price)
        suffix = " · VIP −30%" if is_vip else ""
        row.append(InlineKeyboardButton(
            text=f"{emoji} {name} · {actual_price} ⭐{suffix}",
            callback_data=f"qgift:{context}:{reference}:{gift_id}",
        ))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([
        InlineKeyboardButton(text=ButtonText.CLOSE, callback_data="qgift:close")
    ])

    await message.answer(
        screen(
            "🎁 Анонимный подарок",
            intro="Подарок будет отправлен без указания вашего имени.",
            footer="Выберите вариант.",
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
    )


def install_question_copy_ui() -> None:
    questions._send_target_screen = send_target_screen
    questions._send_gift_screen = send_gift_screen
    questions._send_write_question_screen = send_write_question_screen
    questions._show_question_gifts = show_question_gifts

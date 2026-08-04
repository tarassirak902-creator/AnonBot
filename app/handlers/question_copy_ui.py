from __future__ import annotations

from html import escape

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
)

from app.core.ui_copy import screen
from app.core.ui_labels import ButtonText, ScreenTitle

from . import questions


def _single_back(callback_data: str, *, text: str = ButtonText.BACK) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text=text, callback_data=callback_data),
        ]]
    )


async def _error(message: Message, title: str, intro: str) -> None:
    await message.answer(
        screen(title, intro=intro),
        parse_mode="HTML",
    )


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
        _single_back("questions:target_home"),
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
        await _error(message, "🎁 Подарки", "Сейчас нет доступных подарков.")
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


def question_link_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📖 Как добавить в профиль",
            callback_data="questions:profile_help",
        )],
        [InlineKeyboardButton(text=ButtonText.BACK, callback_data="questions:home")],
    ])


def question_profile_help_inline() -> InlineKeyboardMarkup:
    return _single_back("questions:link", text="⬅️ К ссылке")


def stars_amount_inline(context: str, reference: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for left, right in ((50, 100), (250, 500)):
        rows.append([
            InlineKeyboardButton(
                text=f"⭐ {left}",
                callback_data=f"qstars:{context}:{reference}:{left}",
            ),
            InlineKeyboardButton(
                text=f"⭐ {right}",
                callback_data=f"qstars:{context}:{reference}:{right}",
            ),
        ])
    rows.append([InlineKeyboardButton(
        text="✍️ Другая сумма",
        callback_data=f"qstars_custom:{context}:{reference}",
    )])
    rows.append([InlineKeyboardButton(
        text=ButtonText.CANCEL,
        callback_data="qstars_close",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def premium_inline(context: str, reference: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="💎 3 месяца · 1000 ⭐",
            callback_data=f"qpremium:{context}:{reference}:3:1000",
        )],
        [InlineKeyboardButton(
            text="💎 6 месяцев · 1500 ⭐",
            callback_data=f"qpremium:{context}:{reference}:6:1500",
        )],
        [InlineKeyboardButton(
            text="💎 12 месяцев · 2500 ⭐",
            callback_data=f"qpremium:{context}:{reference}:12:2500",
        )],
        [InlineKeyboardButton(text=ButtonText.CANCEL, callback_data="qpremium_close")],
    ])


async def send_question_stars_invoice(
    message: Message,
    *,
    context: str,
    reference: str,
    amount: int,
) -> None:
    if amount < 1 or amount > 10_000:
        await _error(
            message,
            "⚠️ Некорректная сумма",
            "Введите целое число от 1 до 10 000 ⭐.",
        )
        return

    receiver_id = await questions._resolve_question_receiver(
        message.from_user.id,
        context,
        reference,
    )
    if not receiver_id:
        await _error(
            message,
            "⚠️ Получатель недоступен",
            "Не удалось определить получателя. Вернитесь назад и повторите действие.",
        )
        return

    invoice_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ Оплатить {amount} ⭐", pay=True)],
        [InlineKeyboardButton(
            text=ButtonText.CANCEL,
            callback_data=f"qstars_invoice_cancel:{context}:{reference}",
        )],
    ])
    invoice = await message.bot.send_invoice(
        chat_id=message.chat.id,
        title=f"⭐ Отправить {amount} звёзд",
        description="Анонимная отправка звёзд через раздел «Вопросы».",
        payload=f"question_stars:{context}:{reference}:{amount}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"Звёзды · {amount}", amount=amount)],
        start_parameter="question-stars",
        reply_markup=invoice_keyboard,
    )
    questions.pending_invoice_message_ids[message.from_user.id] = invoice.message_id


async def send_question_premium_invoice(
    message: Message,
    *,
    context: str,
    reference: str,
    months: int,
    stars: int,
) -> None:
    allowed = {3: 1000, 6: 1500, 12: 2500}
    if allowed.get(months) != stars:
        await _error(
            message,
            "⚠️ Вариант недоступен",
            "Выберите другой срок Telegram Premium.",
        )
        return

    receiver_id = await questions._resolve_question_receiver(
        message.from_user.id,
        context,
        reference,
    )
    if not receiver_id:
        await _error(
            message,
            "⚠️ Получатель недоступен",
            "Не удалось определить получателя. Вернитесь назад и повторите действие.",
        )
        return

    invoice_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ Оплатить {stars} ⭐", pay=True)],
        [InlineKeyboardButton(
            text=ButtonText.CANCEL,
            callback_data=f"qpremium_invoice_cancel:{context}:{reference}",
        )],
    ])
    invoice = await message.bot.send_invoice(
        chat_id=message.chat.id,
        title=f"💎 Premium на {months} месяцев",
        description="Анонимный подарок Telegram Premium через раздел «Вопросы».",
        payload=f"question_premium:{context}:{reference}:{months}:{stars}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(
            label=f"Telegram Premium · {months} месяцев",
            amount=stars,
        )],
        start_parameter="question-premium",
        reply_markup=invoice_keyboard,
    )
    questions.pending_invoice_message_ids[message.from_user.id] = invoice.message_id


async def return_from_gift_menu(message: Message, state) -> None:
    data = await state.get_data()
    return_to = data.get("gift_return_to")
    if return_to == "target":
        await send_target_screen(message, state)
        return
    if return_to == "question":
        public_id = data.get("current_question_id")
        row = await questions.db.get_question_by_public_id(public_id)
        await state.set_state(questions.AnonymousQuestionFlow.viewing_question)
        await message.answer(
            screen("❓ Вопрос", intro="Вы вернулись к просмотру вопроса."),
            parse_mode="HTML",
            reply_markup=questions.question_card_menu(
                author_revealed=bool(row[10]) if row else False,
            ),
        )
        return
    if return_to == "answer":
        await state.set_state(questions.AnonymousQuestionFlow.viewing_answer)
        await message.answer(
            screen("💬 Ответ", intro="Вы вернулись к просмотру ответа."),
            parse_mode="HTML",
            reply_markup=questions.question_answer_menu(),
        )
        return
    await questions._send_questions_home(message, state)


def install_question_copy_ui() -> None:
    questions._send_target_screen = send_target_screen
    questions._send_gift_screen = send_gift_screen
    questions._send_write_question_screen = send_write_question_screen
    questions._show_question_gifts = show_question_gifts
    questions.question_link_inline = question_link_inline
    questions.question_profile_help_inline = question_profile_help_inline
    questions._stars_amount_inline = stars_amount_inline
    questions._premium_inline = premium_inline
    questions._send_question_stars_invoice = send_question_stars_invoice
    questions._send_question_premium_invoice = send_question_premium_invoice
    questions._return_from_gift_menu = return_from_gift_menu

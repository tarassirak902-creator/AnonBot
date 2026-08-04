from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.fsm.context import FSMContext

from app.core.ui_copy import metric, screen, section
from app.core.ui_labels import ButtonText
from app.services.question_presentation import (
    build_answer_list_items,
    build_question_list_items,
)

from . import questions


def _inline(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def questions_home_inline() -> InlineKeyboardMarkup:
    return _inline([
        [InlineKeyboardButton(text="📥 Открыть входящие вопросы", callback_data="questions:mine")],
        [InlineKeyboardButton(text="💬 Посмотреть полученные ответы", callback_data="questions:answers")],
        [InlineKeyboardButton(text="🔗 Поделиться моей ссылкой", callback_data="questions:link")],
        [InlineKeyboardButton(text="🏠 На главную", callback_data="nav_main_menu")],
    ])


def questions_page_inline(rows, has_prev: bool, has_next: bool, offset: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=item.text, callback_data=item.callback_data)]
        for item in build_question_list_items(rows)
    ]
    nav: list[InlineKeyboardButton] = []
    if has_prev:
        nav.append(InlineKeyboardButton(text="⬅️ Раньше", callback_data=f"questions:page:{max(0, offset-questions.PAGE_SIZE)}"))
    if has_next:
        nav.append(InlineKeyboardButton(text="Позже ➡️", callback_data=f"questions:page:{offset+questions.PAGE_SIZE}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="⬅️ В раздел вопросов", callback_data="questions:home")])
    return _inline(buttons)


def answers_page_inline(rows, has_prev: bool, has_next: bool, offset: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=item.text, callback_data=item.callback_data)]
        for item in build_answer_list_items(rows)
    ]
    nav: list[InlineKeyboardButton] = []
    if has_prev:
        nav.append(InlineKeyboardButton(text="⬅️ Раньше", callback_data=f"questions:answers_page:{max(0, offset-questions.PAGE_SIZE)}"))
    if has_next:
        nav.append(InlineKeyboardButton(text="Позже ➡️", callback_data=f"questions:answers_page:{offset+questions.PAGE_SIZE}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="⬅️ В раздел вопросов", callback_data="questions:home")])
    return _inline(buttons)


def question_card_inline(author_revealed: bool = False) -> InlineKeyboardMarkup:
    author_text = "👤 Открыть автора" if author_revealed else "👤 Узнать автора · 100 ⭐"
    author_cb = "questions:show_author" if author_revealed else "questions:buy_reveal"
    return _inline([
        [InlineKeyboardButton(text="💬 Ответить на вопрос", callback_data="questions:reply")],
        [
            InlineKeyboardButton(text="🎁 Отправить подарок", callback_data="questions:gift"),
            InlineKeyboardButton(text=author_text, callback_data=author_cb),
        ],
        [InlineKeyboardButton(text="⬅️ К входящим", callback_data="questions:back_mine")],
    ])


def answer_card_inline() -> InlineKeyboardMarkup:
    return _inline([
        [InlineKeyboardButton(text="❓ Задать новый вопрос", callback_data="questions:ask_again")],
        [InlineKeyboardButton(text="🎁 Отправить подарок", callback_data="questions:answer_gift")],
        [InlineKeyboardButton(text="⬅️ К ответам", callback_data="questions:back_answers")],
    ])


def question_link_inline() -> InlineKeyboardMarkup:
    return _inline([
        [InlineKeyboardButton(text="📖 Как добавить ссылку в профиль", callback_data="questions:profile_help")],
        [InlineKeyboardButton(text="⬅️ В раздел вопросов", callback_data="questions:home")],
    ])


def question_profile_help_inline() -> InlineKeyboardMarkup:
    return _inline([[InlineKeyboardButton(text="⬅️ К моей ссылке", callback_data="questions:link")]])


def stars_amount_inline(context: str, reference: str) -> InlineKeyboardMarkup:
    return _inline([
        [
            InlineKeyboardButton(text="⭐ 50", callback_data=f"qstars:{context}:{reference}:50"),
            InlineKeyboardButton(text="⭐ 100", callback_data=f"qstars:{context}:{reference}:100"),
        ],
        [
            InlineKeyboardButton(text="⭐ 250", callback_data=f"qstars:{context}:{reference}:250"),
            InlineKeyboardButton(text="⭐ 500", callback_data=f"qstars:{context}:{reference}:500"),
        ],
        [InlineKeyboardButton(text="✍️ Ввести другую сумму", callback_data=f"qstars_custom:{context}:{reference}")],
        [InlineKeyboardButton(text=ButtonText.CANCEL, callback_data="qstars_close")],
    ])


def premium_inline(context: str, reference: str) -> InlineKeyboardMarkup:
    return _inline([
        [InlineKeyboardButton(text="💎 3 месяца · 1000 ⭐", callback_data=f"qpremium:{context}:{reference}:3:1000")],
        [InlineKeyboardButton(text="💎 6 месяцев · 1500 ⭐", callback_data=f"qpremium:{context}:{reference}:6:1500")],
        [InlineKeyboardButton(text="💎 12 месяцев · 2500 ⭐", callback_data=f"qpremium:{context}:{reference}:12:2500")],
        [InlineKeyboardButton(text=ButtonText.CANCEL, callback_data="qpremium_close")],
    ])


async def send_questions_home(message: Message, state: FSMContext) -> None:
    await questions._clear_question_screen(message, state)
    await state.set_state(questions.AnonymousQuestionFlow.questions_home)
    total, unread = await questions.db.count_user_questions(message.from_user.id)
    answers_total, answers_unread = await questions.db.count_user_question_answers(message.from_user.id)
    stats = await questions.db.get_question_user_stats(message.from_user.id)

    unread_line = []
    if unread:
        unread_line.append(f"🆕 <b>{unread}</b> новых вопросов")
    if answers_unread:
        unread_line.append(f"🔔 <b>{answers_unread}</b> новых ответов")
    intro = " · ".join(unread_line) if unread_line else "Новых сообщений пока нет."

    text = screen(
        "❓ Анонимные вопросы",
        intro=intro,
        sections=(
            section("Ваша активность", (
                metric("📥", "Входящих вопросов", total),
                metric("💬", "Полученных ответов", answers_total),
                metric("🔗", "Переходов по ссылке", stats["visits"]),
            )),
            section("Получено через ссылку", (
                metric("🎁", "Подарков", stats["gifts"]),
                metric("⭐", "Звёзд", stats["stars"]),
                metric("💎", "Premium", stats["premium"]),
            )),
        ),
        footer="Откройте нужный раздел или поделитесь ссылкой.",
    )
    sent = await questions.send_brand_card(message, "questions", text, questions_home_inline())
    await questions._remember_question_screen(state, sent)


async def send_questions_page(message: Message, state: FSMContext, offset: int) -> None:
    await questions._clear_question_screen(message, state)
    rows_plus = await questions.db.get_user_questions(
        message.from_user.id,
        limit=questions.PAGE_SIZE + 1,
        offset=offset,
    )
    has_next = len(rows_plus) > questions.PAGE_SIZE
    rows = rows_plus[:questions.PAGE_SIZE]
    has_prev = offset > 0
    await state.set_state(questions.AnonymousQuestionFlow.browsing_questions)
    await state.update_data(question_list_offset=offset)
    text = screen(
        "📥 Входящие вопросы",
        intro=("Выберите вопрос, чтобы открыть карточку." if rows else "Здесь пока пусто."),
        footer=(f"На странице: {len(rows)}" if rows else "Поделитесь своей ссылкой — новые вопросы появятся здесь."),
    )
    content = await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=questions_page_inline(rows, has_prev, has_next, offset),
    )
    await questions._remember_question_screen(state, content)


async def send_answers_page(message: Message, state: FSMContext, offset: int) -> None:
    await questions._clear_question_screen(message, state)
    rows_plus = await questions.db.get_user_question_answers(
        message.from_user.id,
        limit=questions.PAGE_SIZE + 1,
        offset=offset,
    )
    has_next = len(rows_plus) > questions.PAGE_SIZE
    rows = rows_plus[:questions.PAGE_SIZE]
    has_prev = offset > 0
    await state.set_state(questions.AnonymousQuestionFlow.browsing_answers)
    await state.update_data(answer_list_offset=offset)
    text = screen(
        "💬 Ответы на ваши вопросы",
        intro=("Выберите ответ, чтобы прочитать его." if rows else "Ответов пока нет."),
        footer=(f"На странице: {len(rows)}" if rows else "Когда получатель ответит, сообщение появится здесь."),
    )
    content = await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=answers_page_inline(rows, has_prev, has_next, offset),
    )
    await questions._remember_question_screen(state, content)


async def return_from_gift_menu(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    return_to = data.get("gift_return_to")
    if return_to == "target":
        await questions._send_target_screen(message, state)
        return
    if return_to == "question":
        public_id = data.get("current_question_id")
        row = await questions.db.get_question_by_public_id(public_id)
        await state.set_state(questions.AnonymousQuestionFlow.viewing_question)
        await message.answer(
            screen("❓ Карточка вопроса", intro="Вы вернулись к вопросу."),
            parse_mode="HTML",
            reply_markup=question_card_inline(author_revealed=bool(row[10]) if row else False),
        )
        return
    if return_to == "answer":
        await state.set_state(questions.AnonymousQuestionFlow.viewing_answer)
        await message.answer(
            screen("💬 Карточка ответа", intro="Вы вернулись к ответу."),
            parse_mode="HTML",
            reply_markup=answer_card_inline(),
        )
        return
    await send_questions_home(message, state)


def install_question_browser_ui() -> None:
    questions._send_questions_home = send_questions_home
    questions._send_questions_page = send_questions_page
    questions._send_answers_page = send_answers_page
    questions._return_from_gift_menu = return_from_gift_menu
    questions.questions_home_inline = questions_home_inline
    questions.questions_page_inline = questions_page_inline
    questions.answers_page_inline = answers_page_inline
    questions.question_card_inline = question_card_inline
    questions.answer_card_inline = answer_card_inline
    questions.question_link_inline = question_link_inline
    questions.question_profile_help_inline = question_profile_help_inline
    questions._stars_amount_inline = stars_amount_inline
    questions._premium_inline = premium_inline

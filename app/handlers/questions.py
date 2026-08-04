from __future__ import annotations

from html import escape

from .shared import *


PAGE_SIZE = 5

# Временный контекст персональной ссылки для кнопки нижнего меню.
# Ключ — Telegram ID пользователя, значение — данные владельца ссылки.
_question_start_targets: dict[int, tuple[str, int, str]] = {}


QUESTION_FLOW_ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets" / "questions"
QUESTION_FLOW_ASSETS = {
    "actions": QUESTION_FLOW_ASSETS_DIR / "question_actions.jpg",
    "gifts": QUESTION_FLOW_ASSETS_DIR / "gift_options.jpg",
    "write": QUESTION_FLOW_ASSETS_DIR / "write_question.png",
}


async def _clear_question_screen(message: Message, state: FSMContext, *, delete_trigger: bool = True) -> None:
    """Удаляет только служебные карточки модуля вопросов и нажатую reply-кнопку."""
    data = await state.get_data()
    ids = data.get("question_screen_message_ids") or []
    if isinstance(ids, int):
        ids = [ids]
    for message_id in ids:
        try:
            await message.bot.delete_message(message.chat.id, int(message_id))
        except Exception:
            pass
    if delete_trigger and message.from_user and not getattr(message.from_user, "is_bot", False):
        try:
            await message.delete()
        except Exception:
            pass
    await state.update_data(question_screen_message_ids=[])


async def _remember_question_screen(state: FSMContext, *messages: Message) -> None:
    await state.update_data(
        question_screen_message_ids=[m.message_id for m in messages if m is not None]
    )


async def _send_question_flow_card(message: Message, card: str, caption: str, reply_markup=None):
    asset = QUESTION_FLOW_ASSETS.get(card)
    try:
        if asset and asset.exists():
            return await message.answer_photo(
                photo=FSInputFile(asset),
                caption=caption,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
    except Exception as exc:
        await db.log_action(message.from_user.id, "question_flow_card_error", f"{card}: {exc}")
    return await message.answer(caption, parse_mode="HTML", reply_markup=reply_markup)


async def _send_target_screen(message: Message, state: FSMContext) -> None:
    await _clear_question_screen(message, state)
    data = await state.get_data()
    name = data.get("question_target_name", "пользователю")
    await state.set_state(AnonymousQuestionFlow.target_menu)
    sent = await _send_question_flow_card(
        message,
        "actions",
        f"❓ <b>Анонимное обращение</b>\n\nВыберите, что хотите отправить пользователю <b>{escape(name)}</b>.",
        question_target_inline(name),
    )
    await _remember_question_screen(state, sent)


async def _send_gift_screen(message: Message, state: FSMContext) -> None:
    await _clear_question_screen(message, state)
    await state.set_state(AnonymousQuestionFlow.gift_menu)
    sent = await _send_question_flow_card(
        message,
        "gifts",
        "🎁 <b>Выберите, что хотите отправить</b>",
        question_gift_inline(),
    )
    await _remember_question_screen(state, sent)


async def _send_write_question_screen(message: Message, state: FSMContext) -> None:
    await _clear_question_screen(message, state)
    data = await state.get_data()
    name = data.get("question_target_name", "пользователю")
    await state.set_state(AnonymousQuestionFlow.waiting_for_question)
    sent = await _send_question_flow_card(
        message,
        "write",
        f"❓ <b>Напишите анонимный вопрос для {escape(name)}</b>\n\nОтправьте одно текстовое сообщение. Получатель не увидит ваше имя.",
        inline_back("questions:target_home"),
    )
    await _remember_question_screen(state, sent)


class AnonymousQuestionFlow(StatesGroup):
    target_menu = State()
    waiting_for_question = State()
    waiting_for_answer = State()
    questions_home = State()
    browsing_questions = State()
    viewing_question = State()
    browsing_answers = State()
    viewing_answer = State()
    link_screen = State()
    profile_help = State()
    gift_menu = State()
    waiting_for_star_amount = State()


def _display_name(owner) -> str:
    first_name = (owner[2] or "").strip()
    username = (owner[1] or "").strip()
    return first_name or (f"@{username}" if username else "пользователю")


async def _send_question_author(message: Message, sender_id: int) -> None:
    try:
        author = await message.bot.get_chat(sender_id)
        full_name = f"{author.first_name or ''} {author.last_name or ''}".strip() or "Не указано"
        username = f"@{author.username}" if author.username else "Не установлен"
        profile_link = f'<a href="tg://user?id={author.id}">Открыть профиль</a>'
        await message.answer(
            "👤 <b>Автор вопроса</b>\n\n"
            f"Имя: <b>{escape(full_name)}</b>\n"
            f"Username: <b>{escape(username)}</b>\n"
            f"Telegram ID: <code>{author.id}</code>\n\n"
            f"{profile_link}",
            parse_mode="HTML",
            reply_markup=question_card_menu(author_revealed=True),
        )
    except Exception:
        await message.answer(
            f'👤 Автор вопроса: <a href="tg://user?id={sender_id}">открыть профиль</a>',
            parse_mode="HTML",
            reply_markup=question_card_menu(author_revealed=True),
        )


def _target_inline(token: str, display_name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"❓ Задать анонимный вопрос {display_name}",
                    callback_data=f"qtarget:{token}",
                )
            ]
        ]
    )


def _questions_list_inline(rows) -> InlineKeyboardMarkup | None:
    if not rows:
        return None
    buttons = []
    for qid, public_id, status, created_at in rows:
        try:
            stamp = datetime.fromisoformat(created_at).strftime("%d.%m.%Y • %H:%M")
        except Exception:
            stamp = created_at
        icon = "🆕" if status == "new" else ("✅" if status == "answered" else "❓")
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{icon} Вопрос №{qid} — {stamp}",
                    callback_data=f"questions:view:{public_id}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _answers_list_inline(rows) -> InlineKeyboardMarkup | None:
    if not rows:
        return None
    buttons = []
    for qid, public_id, answered_at, answer_read_at in rows:
        try:
            stamp = datetime.fromisoformat(answered_at).strftime("%d.%m.%Y • %H:%M")
        except Exception:
            stamp = answered_at or "—"
        icon = "🆕" if not answer_read_at else "💬"
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{icon} Ответ на вопрос №{qid} — {stamp}",
                    callback_data=f"questions:answer_view:{public_id}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _show_question_gifts(
    message: Message,
    *,
    context: str,
    reference: str,
) -> None:
    """Показывает тот же каталог подарков, что используется в анонимном чате."""
    gifts = await db.get_all_gifts()
    if not gifts:
        await message.answer("Нет доступных подарков.")
        return

    is_vip = await db.is_user_vip(message.from_user.id)
    keyboard: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for gift_id, name, emoji, price in gifts:
        actual_price = int(price * 0.7) if is_vip else int(price)
        price_text = f"{actual_price} ⭐ (-30%)" if is_vip else f"{price} ⭐"
        row.append(
            InlineKeyboardButton(
                text=f"{emoji} {name} — {price_text}",
                callback_data=f"qgift:{context}:{reference}:{gift_id}",
            )
        )
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append(
        [InlineKeyboardButton(text="не заслужила😜", callback_data="qgift:close")]
    )
    await message.answer(
        "🎁 Выберите подарок. Он будет отправлен анонимно через раздел «Вопросы»:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
    )


async def _send_question_vip_invoice(
    message: Message,
    *,
    context: str,
    reference: str,
) -> None:
    """Выставляет счёт на подарочный VIP на 30 дней через анонимные вопросы."""
    buyer_id = message.from_user.id
    receiver_id: int | None = None

    if context == "t":
        try:
            receiver_id = int(reference)
        except (TypeError, ValueError):
            receiver_id = None
        if receiver_id == buyer_id or not receiver_id or not await db.get_question_owner_by_id(receiver_id):
            receiver_id = None
    elif context in {"q", "a"}:
        question = await db.get_question_by_public_id(reference)
        if question:
            if context == "q" and int(question[3]) == buyer_id:
                receiver_id = int(question[2])
            elif context == "a" and int(question[2]) == buyer_id:
                receiver_id = int(question[3])

    if not receiver_id:
        await message.answer("Получатель недоступен.")
        return

    price = 100
    days = 30
    invoice_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Оплатить {price} ⭐", pay=True)],
            [InlineKeyboardButton(text="↩️ Передумал", callback_data=f"qvip_cancel:{context}:{reference}")],
        ]
    )
    invoice = await message.bot.send_invoice(
        chat_id=message.chat.id,
        title="👑 VIP на 30 дней",
        description="Анонимный подарок VIP через раздел «Вопросы».",
        payload=f"question_vip:{context}:{reference}:{days}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="VIP на 30 дней", amount=price)],
        start_parameter="question-vip",
        reply_markup=invoice_keyboard,
    )
    pending_invoice_message_ids[buyer_id] = invoice.message_id



async def _resolve_question_receiver(user_id: int, context: str, reference: str) -> int | None:
    receiver_id: int | None = None
    if context == "t":
        try:
            candidate = int(reference)
        except (TypeError, ValueError):
            candidate = 0
        if candidate and candidate != user_id and await db.get_question_owner_by_id(candidate):
            receiver_id = candidate
    elif context in {"q", "a"}:
        question = await db.get_question_by_public_id(reference)
        if question:
            if context == "q" and int(question[3]) == user_id:
                receiver_id = int(question[2])
            elif context == "a" and int(question[2]) == user_id:
                receiver_id = int(question[3])
    return receiver_id


async def _open_question_gift_menu(
    message: Message,
    state: FSMContext,
    *,
    context: str,
    reference: str,
    return_to: str,
) -> None:
    receiver_id = await _resolve_question_receiver(message.from_user.id, context, reference)
    if not receiver_id:
        await message.answer("Получатель недоступен.")
        return
    await state.set_state(AnonymousQuestionFlow.gift_menu)
    await state.update_data(
        gift_context=context,
        gift_reference=reference,
        gift_return_to=return_to,
    )
    await _send_gift_screen(message, state)


def _stars_amount_inline(context: str, reference: str) -> InlineKeyboardMarkup:
    rows = []
    for left, right in ((50, 100), (250, 500)):
        rows.append([
            InlineKeyboardButton(text=f"⭐ {left}", callback_data=f"qstars:{context}:{reference}:{left}"),
            InlineKeyboardButton(text=f"⭐ {right}", callback_data=f"qstars:{context}:{reference}:{right}"),
        ])
    rows.append([InlineKeyboardButton(text="✍️ Другая сумма", callback_data=f"qstars_custom:{context}:{reference}")])
    rows.append([InlineKeyboardButton(text="↩️ Передумал", callback_data="qstars_close")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _premium_inline(context: str, reference: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 3 месяца — 1000 ⭐", callback_data=f"qpremium:{context}:{reference}:3:1000")],
        [InlineKeyboardButton(text="💎 6 месяцев — 1500 ⭐", callback_data=f"qpremium:{context}:{reference}:6:1500")],
        [InlineKeyboardButton(text="💎 12 месяцев — 2500 ⭐", callback_data=f"qpremium:{context}:{reference}:12:2500")],
        [InlineKeyboardButton(text="↩️ Передумал", callback_data="qpremium_close")],
    ])


async def _return_from_gift_menu(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    return_to = data.get("gift_return_to")
    if return_to == "target":
        await _send_target_screen(message, state)
    elif return_to == "question":
        public_id = data.get("current_question_id")
        row = await db.get_question_by_public_id(public_id)
        await state.set_state(AnonymousQuestionFlow.viewing_question)
        await message.answer(
            "↩️ Вы вернулись к вопросу.",
            reply_markup=question_card_menu(author_revealed=bool(row[10]) if row else False),
        )
    elif return_to == "answer":
        await state.set_state(AnonymousQuestionFlow.viewing_answer)
        await message.answer("↩️ Вы вернулись к ответу.", reply_markup=question_answer_menu())
    else:
        await _send_questions_home(message, state)


async def _send_question_stars_invoice(
    message: Message,
    *,
    context: str,
    reference: str,
    amount: int,
) -> None:
    if amount < 1 or amount > 10000:
        await message.answer("Укажите сумму от 1 до 10 000 ⭐.")
        return
    receiver_id = await _resolve_question_receiver(message.from_user.id, context, reference)
    if not receiver_id:
        await message.answer("Получатель недоступен.")
        return
    invoice_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Оплатить {amount} ⭐", pay=True)],
        [InlineKeyboardButton(text="↩️ Передумал", callback_data=f"qstars_invoice_cancel:{context}:{reference}")],
    ])
    invoice = await message.bot.send_invoice(
        chat_id=message.chat.id,
        title=f"⭐ Звёзды — {amount}",
        description="Анонимная отправка звёзд через раздел «Вопросы».",
        payload=f"question_stars:{context}:{reference}:{amount}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"Звёзды — {amount}", amount=amount)],
        start_parameter="question-stars",
        reply_markup=invoice_keyboard,
    )
    pending_invoice_message_ids[message.from_user.id] = invoice.message_id


async def _send_question_premium_invoice(
    message: Message,
    *,
    context: str,
    reference: str,
    months: int,
    stars: int,
) -> None:
    allowed = {3: 1000, 6: 1500, 12: 2500}
    if allowed.get(months) != stars:
        await message.answer("Выбранный вариант Telegram Premium недоступен.")
        return
    receiver_id = await _resolve_question_receiver(message.from_user.id, context, reference)
    if not receiver_id:
        await message.answer("Получатель недоступен.")
        return
    invoice_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Оплатить {stars} ⭐", pay=True)],
        [InlineKeyboardButton(text="↩️ Передумал", callback_data=f"qpremium_invoice_cancel:{context}:{reference}")],
    ])
    invoice = await message.bot.send_invoice(
        chat_id=message.chat.id,
        title=f"💎 Telegram Premium на {months} месяцев",
        description="Анонимный подарок Telegram Premium через раздел «Вопросы».",
        payload=f"question_premium:{context}:{reference}:{months}:{stars}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"Telegram Premium на {months} месяцев", amount=stars)],
        start_parameter="question-premium",
        reply_markup=invoice_keyboard,
    )
    pending_invoice_message_ids[message.from_user.id] = invoice.message_id


async def _send_questions_home(message: Message, state: FSMContext) -> None:
    await _clear_question_screen(message, state)
    await state.set_state(AnonymousQuestionFlow.questions_home)
    total, _unread = await db.count_user_questions(message.from_user.id)
    answers_total, _answers_unread = await db.count_user_question_answers(message.from_user.id)
    stats = await db.get_question_user_stats(message.from_user.id)
    text = (
        "❓ <b>Анонимные вопросы</b>\n\n"
        "Здесь находятся вопросы, которые вам задали по персональной ссылке, "
        "а также ответы на вопросы, отправленные вами и статистика.\n\n"
        f"🔗 Переходов по ссылке: <b>{stats['visits']}</b>\n"
        f"📚 Всего вопросов: <b>{total}</b>\n"
        f"🗂 Всего ответов: <b>{answers_total}</b>\n"
        f"🎁 Получено подарков: <b>{stats['gifts']}</b>\n"
        f"⭐ Получено звёзд: <b>{stats['stars']}</b>\n"
        f"💎 Telegram Premium: <b>{stats['premium']}</b>"
    )
    sent = await send_brand_card(message, "questions", text, questions_home_inline())
    await _remember_question_screen(state, sent)


async def _send_questions_page(message: Message, state: FSMContext, offset: int) -> None:
    await _clear_question_screen(message, state)
    rows_plus = await db.get_user_questions(message.from_user.id, limit=PAGE_SIZE + 1, offset=offset)
    has_next = len(rows_plus) > PAGE_SIZE
    rows = rows_plus[:PAGE_SIZE]
    has_prev = offset > 0
    await state.set_state(AnonymousQuestionFlow.browsing_questions)
    await state.update_data(question_list_offset=offset)
    text = "📥 <b>Мои вопросы</b>\n\n" + ("Выберите вопрос из списка ниже." if rows else "У вас пока нет вопросов.")
    content = await message.answer(text, parse_mode="HTML", reply_markup=questions_page_inline(rows, has_prev, has_next, offset))
    await _remember_question_screen(state, content)


async def _send_answers_page(message: Message, state: FSMContext, offset: int) -> None:
    await _clear_question_screen(message, state)
    rows_plus = await db.get_user_question_answers(message.from_user.id, limit=PAGE_SIZE + 1, offset=offset)
    has_next = len(rows_plus) > PAGE_SIZE
    rows = rows_plus[:PAGE_SIZE]
    has_prev = offset > 0
    await state.set_state(AnonymousQuestionFlow.browsing_answers)
    await state.update_data(answer_list_offset=offset)
    text = "💬 <b>Ответы на мои вопросы</b>\n\n" + ("Выберите ответ из списка ниже." if rows else "Вам пока не ответили на отправленные вопросы.")
    content = await message.answer(text, parse_mode="HTML", reply_markup=answers_page_inline(rows, has_prev, has_next, offset))
    await _remember_question_screen(state, content)


async def show_question_entry_after_start(message: Message, token: str, owner) -> None:
    """Главный экран после start=ask_: одна карточка и персональная reply-кнопка."""
    display_name = _display_name(owner)
    owner_id = int(owner[0])
    _question_start_targets[message.from_user.id] = (token, owner_id, display_name)

    welcome = (
        "👻 <b>Добро пожаловать в CASPER!</b>\n\n"
        "Я помогу вам найти нового собеседника, сыграть в мини-игры, "
        "посмотреть свою анкету и получить подарки.\n\n"
        "Выберите нужный раздел ниже 💜"
    )

    await send_brand_card(
        message,
        "main_menu",
        welcome,
        main_menu_with_question(display_name, message.from_user.id in ADMIN_IDS),
    )


@router.message(F.text.startswith("❓ Задать анонимный вопрос "))
async def open_question_target_from_menu(message: Message, state: FSMContext):
    target = _question_start_targets.get(message.from_user.id)
    if not target:
        await message.answer("Персональная ссылка устарела. Откройте её заново.")
        return

    token, owner_id, display_name = target
    owner = await db.get_question_owner_by_token(token)
    if not owner or not int(owner[4] or 0):
        _question_start_targets.pop(message.from_user.id, None)
        await message.answer("Ссылка недоступна")
        return
    if owner_id == message.from_user.id:
        await message.answer("Нельзя задать вопрос самому себе")
        return

    _question_start_targets.pop(message.from_user.id, None)
    try:
        await message.delete()
    except Exception:
        pass
    await hide_reply_keyboard(message)
    await state.set_state(AnonymousQuestionFlow.target_menu)
    await state.update_data(
        question_target_id=owner_id,
        question_target_token=token,
        question_target_name=display_name,
    )
    await _send_target_screen(message, state)


@router.callback_query(F.data.startswith("qtarget:"))
async def open_question_target(callback: CallbackQuery, state: FSMContext):
    token = callback.data.split(":", 1)[1]
    owner = await db.get_question_owner_by_token(token)
    if not owner or not int(owner[4] or 0):
        await callback.answer("Ссылка недоступна", show_alert=True)
        return
    if int(owner[0]) == callback.from_user.id:
        await callback.answer("Нельзя задать вопрос самому себе", show_alert=True)
        return
    display_name = _display_name(owner)

    # После входа в ветку персонального обращения нижнее главное меню
    # скрывается один раз; далее вся навигация работает только inline.
    await hide_reply_keyboard(callback.message)

    await state.set_state(AnonymousQuestionFlow.target_menu)
    await state.update_data(
        question_target_id=int(owner[0]),
        question_target_token=token,
        question_target_name=display_name,
    )
    try:
        await callback.message.delete()
    except Exception:
        pass
    await _send_target_screen(callback.message, state)
    await callback.answer()


@router.message(AnonymousQuestionFlow.target_menu, F.text == "❓ Задать вопрос")
async def begin_question(message: Message, state: FSMContext):
    await _send_write_question_screen(message, state)


@router.message(AnonymousQuestionFlow.waiting_for_question, F.text == "⬅️ Назад")
async def back_to_target_actions(message: Message, state: FSMContext):
    await _send_target_screen(message, state)


@router.message(AnonymousQuestionFlow.waiting_for_question, F.text)
async def save_question(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text or len(text) > 1500:
        await message.answer("Вопрос должен содержать от 1 до 1500 символов.")
        return
    data = await state.get_data()
    receiver_id = int(data["question_target_id"])
    name = data.get("question_target_name", "пользователю")
    public_id = await db.create_anonymous_question(message.from_user.id, receiver_id, text)
    active_chat = await db.get_partner(receiver_id)
    try:
        if active_chat:
            await db.set_question_chat_pending(public_id, True)
            await message.bot.send_message(
                receiver_id,
                "❓ Пока вы общаетесь в анонимном чате, кто-то вне чата задал вам новый анонимный вопрос.\n\n"
                "Прочитать его можно после завершения текущего диалога.",
                parse_mode="HTML",
            )
        else:
            await message.bot.send_message(
                receiver_id,
                "❓ Вам задали новый анонимный вопрос.\n\nОткройте раздел «Вопросы» в главном меню.",
                parse_mode="HTML",
            )
    except Exception:
        pass
    await db.log_action(message.from_user.id, "question_sent", f"question={public_id}; receiver={receiver_id}")
    await state.set_state(AnonymousQuestionFlow.target_menu)
    await message.answer(
        "✅ <b>Вопрос успешно отправлен!</b>\n\n"
        "Теперь остаётся дождаться ответа.\n\n"
        "Ваше имя осталось анонимным.",
        parse_mode="HTML",
        reply_markup=question_target_inline(name),
    )


@router.message(AnonymousQuestionFlow.target_menu, F.text == "🎁 Подарок")
async def target_open_gift_menu(message: Message, state: FSMContext):
    data = await state.get_data()
    receiver_id = data.get("question_target_id")
    await _open_question_gift_menu(
        message,
        state,
        context="t",
        reference=str(int(receiver_id)) if receiver_id else "0",
        return_to="target",
    )


@router.message(AnonymousQuestionFlow.gift_menu, F.text == "🎁 Подарок")
async def gift_menu_regular(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.update_data(gift_subscreen="regular")
    await message.answer("⬅️ Вы можете вернуться назад.", reply_markup=question_back_menu())
    await _show_question_gifts(
        message,
        context=str(data.get("gift_context")),
        reference=str(data.get("gift_reference")),
    )


@router.message(AnonymousQuestionFlow.gift_menu, F.text == "⭐ Звёзды")
async def gift_menu_stars(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.update_data(gift_subscreen="stars")
    context = str(data.get("gift_context"))
    reference = str(data.get("gift_reference"))
    await message.answer("⬅️ Вы можете вернуться назад.", reply_markup=question_back_menu())
    await message.answer(
        "⭐ <b>Выберите количество звёзд</b>",
        parse_mode="HTML",
        reply_markup=_stars_amount_inline(context, reference),
    )


@router.message(AnonymousQuestionFlow.gift_menu, F.text == "👑 VIP статус")
async def gift_menu_vip(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.update_data(gift_subscreen="vip")
    await _send_question_vip_invoice(
        message,
        context=str(data.get("gift_context")),
        reference=str(data.get("gift_reference")),
    )


@router.message(AnonymousQuestionFlow.gift_menu, F.text == "💎 Telegram Premium")
async def gift_menu_premium(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.update_data(gift_subscreen="premium")
    context = str(data.get("gift_context"))
    reference = str(data.get("gift_reference"))
    await message.answer("⬅️ Вы можете вернуться назад.", reply_markup=question_back_menu())
    await message.answer(
        "💎 <b>Выберите срок Telegram Premium</b>",
        parse_mode="HTML",
        reply_markup=_premium_inline(context, reference),
    )


@router.message(AnonymousQuestionFlow.gift_menu, F.text == "⬅️ Назад")
async def gift_menu_back(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("gift_subscreen"):
        await state.update_data(gift_subscreen=None)
        await _send_gift_screen(message, state)
        return
    await _return_from_gift_menu(message, state)


@router.callback_query(F.data.startswith("qstars:") & ~F.data.endswith(":close"))
async def choose_question_stars(callback: CallbackQuery):
    try:
        _, context, reference, amount_raw = callback.data.split(":", 3)
        amount = int(amount_raw)
    except (TypeError, ValueError):
        await callback.answer("Некорректная сумма.", show_alert=True)
        return
    try:
        await callback.message.delete()
    except Exception:
        pass
    await _send_question_stars_invoice(callback.message, context=context, reference=reference, amount=amount)
    await callback.answer()


@router.callback_query(F.data.startswith("qstars_custom:"))
async def custom_question_stars(callback: CallbackQuery, state: FSMContext):
    _, context, reference = callback.data.split(":", 2)
    await state.set_state(AnonymousQuestionFlow.waiting_for_star_amount)
    await state.update_data(gift_context=context, gift_reference=reference)
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(
        "⭐ Введите количество звёзд от 1 до 10 000.",
        reply_markup=question_custom_stars_menu(),
    )
    await callback.answer()


@router.message(AnonymousQuestionFlow.waiting_for_star_amount, F.text == "⬅️ Назад")
async def custom_question_stars_back(message: Message, state: FSMContext):
    await state.update_data(gift_subscreen=None)
    await _send_gift_screen(message, state)


@router.message(AnonymousQuestionFlow.waiting_for_star_amount, F.text)
async def custom_question_stars_amount(message: Message, state: FSMContext):
    raw = (message.text or "").replace("⭐", "").replace(" ", "")
    try:
        amount = int(raw)
    except ValueError:
        await message.answer("Введите целое число от 1 до 10 000.")
        return
    data = await state.get_data()
    await _send_question_stars_invoice(
        message,
        context=str(data.get("gift_context")),
        reference=str(data.get("gift_reference")),
        amount=amount,
    )
    await state.set_state(AnonymousQuestionFlow.gift_menu)


@router.callback_query(F.data == "qstars_close")
async def close_question_stars(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("qpremium:"))
async def choose_question_premium(callback: CallbackQuery):
    try:
        _, context, reference, months_raw, stars_raw = callback.data.split(":", 4)
        months, stars = int(months_raw), int(stars_raw)
    except (TypeError, ValueError):
        await callback.answer("Некорректный вариант.", show_alert=True)
        return
    try:
        await callback.message.delete()
    except Exception:
        pass
    await _send_question_premium_invoice(
        callback.message,
        context=context,
        reference=reference,
        months=months,
        stars=stars,
    )
    await callback.answer()


@router.callback_query(F.data == "qpremium_close")
async def close_question_premium(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("qstars_invoice_cancel:"))
async def cancel_question_stars_invoice(callback: CallbackQuery, state: FSMContext):
    pending_invoice_message_ids.pop(callback.from_user.id, None)
    try:
        _, context, reference = callback.data.split(":", 2)
    except ValueError:
        context, reference = "", ""
    try:
        await callback.message.delete()
    except Exception:
        pass
    await state.set_state(AnonymousQuestionFlow.gift_menu)
    await state.update_data(gift_subscreen="stars", gift_context=context, gift_reference=reference)
    await callback.message.answer("⬅️ Вы можете вернуться назад.", reply_markup=question_back_menu())
    await callback.message.answer("⭐ <b>Выберите количество звёзд</b>", parse_mode="HTML", reply_markup=_stars_amount_inline(context, reference))
    await callback.answer("Оплата отменена")


@router.callback_query(F.data.startswith("qpremium_invoice_cancel:"))
async def cancel_question_premium_invoice(callback: CallbackQuery, state: FSMContext):
    pending_invoice_message_ids.pop(callback.from_user.id, None)
    try:
        _, context, reference = callback.data.split(":", 2)
    except ValueError:
        context, reference = "", ""
    try:
        await callback.message.delete()
    except Exception:
        pass
    await state.set_state(AnonymousQuestionFlow.gift_menu)
    await state.update_data(gift_subscreen="premium", gift_context=context, gift_reference=reference)
    await callback.message.answer("⬅️ Вы можете вернуться назад.", reply_markup=question_back_menu())
    await callback.message.answer("💎 <b>Выберите срок Telegram Premium</b>", parse_mode="HTML", reply_markup=_premium_inline(context, reference))
    await callback.answer("Оплата отменена")


@router.callback_query(F.data == "qgift:close")
async def close_question_gifts(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()


@router.callback_query(F.data.startswith("qgift:") & ~F.data.endswith(":close"))
async def buy_question_gift(callback: CallbackQuery):
    try:
        _, context, reference, gift_id_raw = callback.data.split(":", 3)
        gift_id = int(gift_id_raw)
    except (TypeError, ValueError):
        await callback.answer("Некорректный подарок.", show_alert=True)
        return

    buyer_id = callback.from_user.id
    receiver_id: int | None = None
    if context == "t":
        try:
            receiver_id = int(reference)
        except ValueError:
            receiver_id = None
        if receiver_id == buyer_id or not await db.get_question_owner_by_id(receiver_id):
            receiver_id = None
    elif context in {"q", "a"}:
        question = await db.get_question_by_public_id(reference)
        if question:
            if context == "q" and int(question[3]) == buyer_id:
                receiver_id = int(question[2])
            elif context == "a" and int(question[2]) == buyer_id:
                receiver_id = int(question[3])

    if not receiver_id:
        await callback.answer("Получатель недоступен.", show_alert=True)
        return

    gift = await db.get_gift(gift_id)
    if not gift:
        await callback.answer("Подарок не найден.", show_alert=True)
        return
    name, emoji, price = gift
    is_vip = await db.is_user_vip(buyer_id)
    actual_price = int(price * 0.7) if is_vip else int(price)

    try:
        await callback.message.delete()
    except Exception:
        pass

    cancel_data = f"qgift_cancel:{context}:{reference}"
    invoice_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Оплатить {actual_price} ⭐", pay=True)],
            [InlineKeyboardButton(text="↩️ Передумал", callback_data=cancel_data)],
        ]
    )
    invoice = await callback.message.bot.send_invoice(
        chat_id=callback.message.chat.id,
        title=f"{emoji} {name}",
        description="Анонимный подарок через раздел «Вопросы».",
        payload=f"question_gift:{context}:{reference}:{gift_id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"Подарок: {name}", amount=actual_price)],
        start_parameter="question-gift",
        reply_markup=invoice_keyboard,
    )
    pending_invoice_message_ids[buyer_id] = invoice.message_id
    await callback.answer()


@router.callback_query(F.data.startswith("qgift_cancel:"))
async def cancel_question_gift(callback: CallbackQuery, state: FSMContext):
    pending_invoice_message_ids.pop(callback.from_user.id, None)
    try:
        await callback.message.delete()
    except Exception:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    try:
        _, context, reference = callback.data.split(":", 2)
    except ValueError:
        context, reference = "", ""
    await state.set_state(AnonymousQuestionFlow.gift_menu)
    await state.update_data(gift_subscreen="regular", gift_context=context, gift_reference=reference)
    await callback.message.answer("⬅️ Вы можете вернуться назад.", reply_markup=question_back_menu())
    await _show_question_gifts(callback.message, context=context, reference=reference)
    await callback.answer("Оплата отменена")


@router.callback_query(F.data.startswith("qvip_cancel:"))
async def cancel_question_vip(callback: CallbackQuery, state: FSMContext):
    pending_invoice_message_ids.pop(callback.from_user.id, None)
    try:
        await callback.message.delete()
    except Exception:
        pass
    await state.set_state(AnonymousQuestionFlow.gift_menu)
    await state.update_data(gift_subscreen=None)
    await _send_gift_screen(callback.message, state)
    await callback.answer("Оплата отменена")


@router.message(F.text == "🏠 Главное меню")
async def question_to_main(message: Message, state: FSMContext):
    await state.clear()
    await show_main_menu_screen(message, message.from_user.id)


@router.message(F.text == "❓ Вопросы")
async def questions_home(message: Message, state: FSMContext):
    await state.clear()
    await hide_reply_keyboard(message)
    await _send_questions_home(message, state)


@router.message(AnonymousQuestionFlow.questions_home, F.text == "📥 Мои вопросы")
async def open_questions_list(message: Message, state: FSMContext):
    await _send_questions_page(message, state, 0)


@router.message(AnonymousQuestionFlow.questions_home, F.text == "💬 Ответы на мои вопросы")
async def open_answers_list(message: Message, state: FSMContext):
    await _send_answers_page(message, state, 0)


@router.message(AnonymousQuestionFlow.questions_home, F.text == "🔗 Моя ссылка")
async def question_link_screen(message: Message, state: FSMContext):
    await _clear_question_screen(message, state)
    token = await db.get_or_create_question_token(message.from_user.id)
    me = await message.bot.get_me()
    link = f"https://t.me/{me.username}?start=ask_{token}"
    text = (
        "🔗 <b>Ваша персональная ссылка</b>\n\n"
        f"<code>{escape(link)}</code>\n\n"
        "Разместите её в описании своего профиля Telegram, чтобы другие пользователи "
        "могли анонимно задать вам вопрос или отправить вам подарок."
    )
    await state.set_state(AnonymousQuestionFlow.link_screen)
    sent = await message.answer(text, parse_mode="HTML", reply_markup=question_link_inline())
    await _remember_question_screen(state, sent)


@router.message(AnonymousQuestionFlow.link_screen, F.text == "📖 Как установить в профиль")
async def question_profile_help(message: Message, state: FSMContext):
    await _clear_question_screen(message, state)
    text = (
        "📖 <b>Как установить ссылку в профиль</b>\n\n"
        "1️⃣ Откройте настройки Telegram.\n\n"
        "2️⃣ Перейдите в раздел изменения профиля.\n\n"
        "3️⃣ Откройте поле «О себе».\n\n"
        "4️⃣ Вставьте туда персональную ссылку из раздела «Моя ссылка».\n\n"
        "Готово ✅ Теперь другие пользователи смогут перейти по ссылке и анонимно "
        "задать вам вопрос или отправить подарок."
    )
    await state.set_state(AnonymousQuestionFlow.profile_help)
    sent = await message.answer(text, parse_mode="HTML", reply_markup=question_profile_help_inline())
    await _remember_question_screen(state, sent)


@router.message(AnonymousQuestionFlow.profile_help, F.text == "⬅️ Назад к ссылке")
async def back_to_question_link(message: Message, state: FSMContext):
    await state.set_state(AnonymousQuestionFlow.questions_home)
    await question_link_screen(message, state)


@router.message(AnonymousQuestionFlow.link_screen, F.text == "⬅️ Назад")
async def back_from_question_link(message: Message, state: FSMContext):
    await _send_questions_home(message, state)


@router.message(F.text == "↩️ Назад к разделу вопросов")
async def back_to_questions_home(message: Message, state: FSMContext):
    await _send_questions_home(message, state)


@router.message(AnonymousQuestionFlow.browsing_questions, F.text == "⬅️ Предыдущие вопросы")
async def previous_questions_page(message: Message, state: FSMContext):
    data = await state.get_data()
    offset = max(0, int(data.get("question_list_offset", 0)) - PAGE_SIZE)
    await _send_questions_page(message, state, offset)


@router.message(AnonymousQuestionFlow.browsing_questions, F.text == "Следующие вопросы ➡️")
async def next_questions_page(message: Message, state: FSMContext):
    data = await state.get_data()
    offset = int(data.get("question_list_offset", 0)) + PAGE_SIZE
    await _send_questions_page(message, state, offset)


@router.message(AnonymousQuestionFlow.browsing_answers, F.text == "⬅️ Предыдущие ответы")
async def previous_answers_page(message: Message, state: FSMContext):
    data = await state.get_data()
    offset = max(0, int(data.get("answer_list_offset", 0)) - PAGE_SIZE)
    await _send_answers_page(message, state, offset)


@router.message(AnonymousQuestionFlow.browsing_answers, F.text == "Следующие ответы ➡️")
async def next_answers_page(message: Message, state: FSMContext):
    data = await state.get_data()
    offset = int(data.get("answer_list_offset", 0)) + PAGE_SIZE
    await _send_answers_page(message, state, offset)


@router.callback_query(F.data.startswith("questions:view:"))
async def question_view(callback: CallbackQuery, state: FSMContext):
    public_id = callback.data.rsplit(":", 1)[1]
    row = await db.get_question_by_public_id(public_id)
    if not row or int(row[3]) != callback.from_user.id:
        await callback.answer("Вопрос не найден", show_alert=True)
        return
    await db.mark_question_read(public_id, callback.from_user.id)
    qid, _, _, _, text, status, answer, created_at, *_ = row
    try:
        stamp = datetime.fromisoformat(created_at).strftime("%d.%m.%Y • %H:%M")
    except Exception:
        stamp = created_at
    card = f"❓ <b>Вопрос №{qid}</b>\n\n📅 {stamp}\n\n«{escape(text)}»"
    if answer:
        card += f"\n\n💬 <b>Ваш ответ:</b>\n{escape(answer)}"

    await _clear_question_screen(callback.message, state, delete_trigger=False)
    await state.set_state(AnonymousQuestionFlow.viewing_question)
    await state.update_data(current_question_id=public_id)

    content = await callback.message.answer(
        card,
        parse_mode="HTML",
        reply_markup=question_card_inline(author_revealed=bool(row[10])),
    )
    await _remember_question_screen(state, content)
    await callback.answer()


@router.message(AnonymousQuestionFlow.viewing_question, F.text == "💬 Ответить")
async def begin_answer_from_menu(message: Message, state: FSMContext):
    data = await state.get_data()
    public_id = data.get("current_question_id")
    row = await db.get_question_by_public_id(public_id)
    if not row or int(row[3]) != message.from_user.id:
        await message.answer("Вопрос не найден.")
        return
    await state.set_state(AnonymousQuestionFlow.waiting_for_answer)
    await state.update_data(answer_question_id=public_id)
    await message.answer(
        "💬 Напишите ответ на вопрос одним текстовым сообщением.",
        reply_markup=answer_writing_menu(),
    )


@router.message(AnonymousQuestionFlow.viewing_question, F.text == "👤 Узнать автора — 100 ⭐")
async def buy_question_author_reveal(message: Message, state: FSMContext):
    data = await state.get_data()
    public_id = data.get("current_question_id")
    row = await db.get_question_by_public_id(public_id)
    if not row or int(row[3]) != message.from_user.id:
        await message.answer("Вопрос не найден.")
        return
    if bool(row[10]):
        await _send_question_author(message, int(row[2]))
        return
    invoice_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Оплатить 100 ⭐", pay=True)],
            [
                InlineKeyboardButton(
                    text="↩️ Передумал",
                    callback_data=f"question_reveal_cancel:{public_id}",
                )
            ],
        ]
    )
    invoice = await message.bot.send_invoice(
        chat_id=message.chat.id,
        title="Раскрытие автора вопроса",
        description="После оплаты вы увидите Telegram-профиль автора этого анонимного вопроса.",
        payload=f"question_reveal:{public_id}",
        currency="XTR",
        prices=[LabeledPrice(label="Узнать автора", amount=100)],
        reply_markup=invoice_keyboard,
    )
    pending_invoice_message_ids[message.from_user.id] = invoice.message_id


@router.callback_query(F.data.startswith("question_reveal_cancel:"))
async def cancel_question_author_reveal(callback: CallbackQuery, state: FSMContext):
    public_id = callback.data.split(":", 1)[1]
    data = await state.get_data()
    if data.get("current_question_id") != public_id:
        await callback.answer("Этот счёт уже неактуален.", show_alert=True)
        return

    pending_invoice_message_ids.pop(callback.from_user.id, None)
    try:
        await callback.message.delete()
    except Exception:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    await callback.answer("Оплата отменена")


@router.message(AnonymousQuestionFlow.viewing_question, F.text == "👤 Посмотреть автора")
async def show_revealed_question_author(message: Message, state: FSMContext):
    data = await state.get_data()
    public_id = data.get("current_question_id")
    row = await db.get_question_by_public_id(public_id)
    if not row or int(row[3]) != message.from_user.id:
        await message.answer("Вопрос не найден.")
        return
    if not bool(row[10]):
        await message.answer("Автор этого вопроса ещё не раскрыт.")
        return
    await _send_question_author(message, int(row[2]))


@router.message(AnonymousQuestionFlow.viewing_question, F.text == "🎁 Подарок")
async def question_open_gift_menu(message: Message, state: FSMContext):
    data = await state.get_data()
    public_id = data.get("current_question_id")
    await _open_question_gift_menu(
        message,
        state,
        context="q",
        reference=str(public_id),
        return_to="question",
    )


@router.message(AnonymousQuestionFlow.viewing_question, F.text == "↩️ Назад к вопросам")
async def back_to_questions_list(message: Message, state: FSMContext):
    data = await state.get_data()
    offset = int(data.get("question_list_offset", 0))
    await _send_questions_page(message, state, offset)


@router.callback_query(F.data.startswith("questions:answer_view:"))
async def question_answer_view(callback: CallbackQuery, state: FSMContext):
    public_id = callback.data.rsplit(":", 1)[1]
    row = await db.get_question_by_public_id(public_id)
    if not row or int(row[2]) != callback.from_user.id or not row[6]:
        await callback.answer("Ответ не найден", show_alert=True)
        return
    await db.mark_question_answer_read(public_id, callback.from_user.id)
    qid, _, _, _, question_text, _, answer_text, _, _, answered_at, _ = row
    try:
        stamp = datetime.fromisoformat(answered_at).strftime("%d.%m.%Y • %H:%M")
    except Exception:
        stamp = answered_at or "—"
    text = (
        f"💬 <b>Ответ на вопрос №{qid}</b>\n\n"
        f"📅 {stamp}\n\n"
        f"<b>Ваш вопрос:</b>\n«{escape(question_text)}»\n\n"
        f"<b>Ответ:</b>\n{escape(answer_text)}"
    )

    await _clear_question_screen(callback.message, state, delete_trigger=False)
    await state.set_state(AnonymousQuestionFlow.viewing_answer)
    await state.update_data(current_answer_question_id=public_id)

    content = await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=answer_card_inline(),
    )
    await _remember_question_screen(state, content)
    await callback.answer()


@router.message(AnonymousQuestionFlow.viewing_answer, F.text == "❓ Задать ещё вопрос")
async def ask_again_from_menu(message: Message, state: FSMContext):
    data = await state.get_data()
    public_id = data.get("current_answer_question_id")
    row = await db.get_question_by_public_id(public_id)
    if not row or int(row[2]) != message.from_user.id:
        await message.answer("Вопрос не найден.")
        return
    owner = await db.get_question_owner_by_id(int(row[3]))
    display_name = _display_name(owner) if owner else "пользователю"
    await state.set_state(AnonymousQuestionFlow.target_menu)
    await state.update_data(question_target_id=int(row[3]), question_target_name=display_name)
    await message.answer(
        f"Выберите действие для <b>{escape(display_name)}</b>.",
        parse_mode="HTML",
        reply_markup=question_target_menu(display_name),
    )


@router.message(AnonymousQuestionFlow.viewing_answer, F.text == "🎁 Подарок")
async def answer_open_gift_menu(message: Message, state: FSMContext):
    data = await state.get_data()
    public_id = data.get("current_answer_question_id")
    await _open_question_gift_menu(
        message,
        state,
        context="a",
        reference=str(public_id),
        return_to="answer",
    )


@router.message(AnonymousQuestionFlow.viewing_answer, F.text == "↩️ Назад к ответам")
async def back_to_answers_list(message: Message, state: FSMContext):
    data = await state.get_data()
    offset = int(data.get("answer_list_offset", 0))
    await _send_answers_page(message, state, offset)


@router.message(AnonymousQuestionFlow.waiting_for_answer, F.text == "↩️ Назад к вопросу")
async def cancel_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    public_id = data.get("answer_question_id")
    row = await db.get_question_by_public_id(public_id)
    if not row or int(row[3]) != message.from_user.id:
        await _send_questions_page(message, state, 0)
        return
    qid, _, _, _, text, status, answer, created_at, *_ = row
    try:
        stamp = datetime.fromisoformat(created_at).strftime("%d.%m.%Y • %H:%M")
    except Exception:
        stamp = created_at
    card = f"❓ <b>Вопрос №{qid}</b>\n\n📅 {stamp}\n\n«{escape(text)}»"
    if answer:
        card += f"\n\n💬 <b>Ваш ответ:</b>\n{escape(answer)}"
    await state.set_state(AnonymousQuestionFlow.viewing_question)
    await state.update_data(current_question_id=public_id)
    await message.answer(card, parse_mode="HTML", reply_markup=question_card_menu(author_revealed=bool(row[10])))


@router.message(AnonymousQuestionFlow.waiting_for_answer, F.text)
async def send_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    public_id = data.get("answer_question_id")
    answer_text = (message.text or "").strip()
    if not answer_text or len(answer_text) > 1500:
        await message.answer("Ответ должен содержать от 1 до 1500 символов.")
        return
    result = await db.answer_question(public_id, message.from_user.id, answer_text)
    if not result:
        await message.answer(
            "Вопрос больше недоступен.",
            reply_markup=main_menu(message.from_user.id in ADMIN_IDS),
        )
        await state.clear()
        return
    sender_id, question_text = result
    active_chat = await db.get_partner(sender_id)
    try:
        if active_chat:
            await db.set_answer_chat_pending(public_id, True)
            await message.bot.send_message(
                sender_id,
                "💬 Пока вы общаетесь в анонимном чате, вам ответили на анонимный вопрос.\n\n"
                "Прочитать ответ можно после завершения текущего диалога.",
                parse_mode="HTML",
            )
        else:
            await message.bot.send_message(
                sender_id,
                "💬 Вам ответили на анонимный вопрос.\n\nОткройте раздел «Вопросы», чтобы прочитать ответ.",
                parse_mode="HTML",
            )
    except Exception:
        pass

    await state.set_state(AnonymousQuestionFlow.viewing_question)
    await state.update_data(current_question_id=public_id)
    await message.answer(
        "✅ <b>Ответ успешно отправлен!</b>\n\n"
        "Отправитель уже получил уведомление.",
        reply_markup=question_card_menu(),
    )


# Совместимость со старыми inline-кнопками уведомлений Stage 2.
@router.callback_query(F.data.startswith("questions:list:"))
async def questions_list_compat(callback: CallbackQuery, state: FSMContext):
    offset = int(callback.data.rsplit(":", 1)[1])
    await _send_questions_page(callback.message, state, offset)
    await callback.answer()


@router.callback_query(F.data.startswith("questions:answers:"))
async def answers_list_compat(callback: CallbackQuery, state: FSMContext):
    offset = int(callback.data.rsplit(":", 1)[1])
    await _send_answers_page(callback.message, state, offset)
    await callback.answer()


@router.callback_query(F.data.startswith(("questions:reveal:", "questions:gift:", "questions:vip:")))
async def question_paid_placeholder(callback: CallbackQuery):
    await callback.answer("Эта функция будет подключена на этапе монетизации.", show_alert=True)


@router.callback_query(F.data == "questions:main")
async def questions_main_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_main_menu_screen(callback.message, callback.from_user.id)
    await callback.answer()

# ===== Inline-навигация анонимных вопросов =====
async def _questions_home_for_callback(callback: CallbackQuery, state: FSMContext):
    await _clear_question_screen(callback.message, state, delete_trigger=False)
    await state.set_state(AnonymousQuestionFlow.questions_home)
    uid = callback.from_user.id
    total, _ = await db.count_user_questions(uid)
    answers_total, _ = await db.count_user_question_answers(uid)
    stats = await db.get_question_user_stats(uid)
    text = (
        "❓ <b>Анонимные вопросы</b>\n\n"
        "Здесь находятся вопросы, которые вам задали по персональной ссылке, "
        "а также ответы на вопросы, отправленные вами и статистика.\n\n"
        f"🔗 Переходов по ссылке: <b>{stats['visits']}</b>\n"
        f"📚 Всего вопросов: <b>{total}</b>\n"
        f"🗂 Всего ответов: <b>{answers_total}</b>\n"
        f"🎁 Получено подарков: <b>{stats['gifts']}</b>\n"
        f"⭐ Получено звёзд: <b>{stats['stars']}</b>\n"
        f"💎 Telegram Premium: <b>{stats['premium']}</b>"
    )
    sent = await send_brand_card(callback.message, "questions", text, questions_home_inline())
    await _remember_question_screen(state, sent)

async def _questions_page_for_callback(callback: CallbackQuery, state: FSMContext, offset: int):
    await _clear_question_screen(callback.message, state, delete_trigger=False)
    rows_plus = await db.get_user_questions(callback.from_user.id, limit=PAGE_SIZE + 1, offset=offset)
    rows = rows_plus[:PAGE_SIZE]
    await state.set_state(AnonymousQuestionFlow.browsing_questions)
    await state.update_data(question_list_offset=offset)
    text = "📥 <b>Мои вопросы</b>\n\n" + ("Выберите вопрос из списка ниже." if rows else "У вас пока нет вопросов.")
    sent = await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=questions_page_inline(rows, offset > 0, len(rows_plus) > PAGE_SIZE, offset),
    )
    await _remember_question_screen(state, sent)

async def _answers_page_for_callback(callback: CallbackQuery, state: FSMContext, offset: int):
    await _clear_question_screen(callback.message, state, delete_trigger=False)
    rows_plus = await db.get_user_question_answers(callback.from_user.id, limit=PAGE_SIZE + 1, offset=offset)
    rows = rows_plus[:PAGE_SIZE]
    await state.set_state(AnonymousQuestionFlow.browsing_answers)
    await state.update_data(answer_list_offset=offset)
    text = "💬 <b>Ответы на мои вопросы</b>\n\n" + ("Выберите ответ из списка ниже." if rows else "Вам пока не ответили на отправленные вопросы.")
    sent = await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=answers_page_inline(rows, offset > 0, len(rows_plus) > PAGE_SIZE, offset),
    )
    await _remember_question_screen(state, sent)

@router.callback_query(F.data == "questions:home")
async def questions_home_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await _questions_home_for_callback(callback, state)

@router.callback_query(F.data == "questions:mine")
async def questions_mine_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await _questions_page_for_callback(callback, state, 0)

@router.callback_query(F.data.startswith("questions:page:"))
async def questions_page_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await _questions_page_for_callback(callback, state, max(0, int(callback.data.rsplit(":", 1)[1])))

@router.callback_query(F.data == "questions:answers")
async def questions_answers_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await _answers_page_for_callback(callback, state, 0)

@router.callback_query(F.data.startswith("questions:answers_page:"))
async def answers_page_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await _answers_page_for_callback(callback, state, max(0, int(callback.data.rsplit(":", 1)[1])))

@router.callback_query(F.data == "questions:link")
async def questions_link_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await _clear_question_screen(callback.message, state, delete_trigger=False)
    token = await db.get_or_create_question_token(callback.from_user.id)
    me = await callback.bot.get_me()
    link = f"https://t.me/{me.username}?start=ask_{token}"
    text = (
        "🔗 <b>Ваша персональная ссылка</b>\n\n"
        f"<code>{escape(link)}</code>\n\n"
        "Разместите её в описании своего профиля Telegram, чтобы другие пользователи "
        "могли анонимно задать вам вопрос или отправить вам подарок."
    )
    await state.set_state(AnonymousQuestionFlow.link_screen)
    sent = await callback.message.answer(text, parse_mode="HTML", reply_markup=question_link_inline())
    await _remember_question_screen(state, sent)

@router.callback_query(F.data == "questions:profile_help")
async def questions_help_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await _clear_question_screen(callback.message, state, delete_trigger=False)
    text = (
        "📖 <b>Как установить ссылку в профиль</b>\n\n"
        "1️⃣ Откройте настройки Telegram.\n\n"
        "2️⃣ Перейдите в раздел изменения профиля.\n\n"
        "3️⃣ Откройте поле «О себе».\n\n"
        "4️⃣ Вставьте туда персональную ссылку из раздела «Моя ссылка».\n\n"
        "Готово ✅"
    )
    await state.set_state(AnonymousQuestionFlow.profile_help)
    sent = await callback.message.answer(text, parse_mode="HTML", reply_markup=question_profile_help_inline())
    await _remember_question_screen(state, sent)


@router.callback_query(F.data == "questions:reply")
async def questions_reply_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    public_id = data.get("current_question_id")
    row = await db.get_question_by_public_id(public_id)
    if not row or int(row[3]) != callback.from_user.id:
        await callback.answer("Вопрос не найден", show_alert=True)
        return
    await state.set_state(AnonymousQuestionFlow.waiting_for_answer)
    await state.update_data(answer_question_id=public_id)
    try:
        await callback.message.edit_text(
            "💬 <b>Напишите ответ на вопрос одним текстовым сообщением.</b>",
            parse_mode="HTML",
            reply_markup=inline_back(f"questions:view:{public_id}", "⬅️ Назад к вопросу"),
        )
    except Exception:
        await callback.message.answer(
            "💬 <b>Напишите ответ на вопрос одним текстовым сообщением.</b>",
            parse_mode="HTML",
            reply_markup=inline_back(f"questions:view:{public_id}", "⬅️ Назад к вопросу"),
        )
    await callback.answer()


@router.callback_query(F.data == "questions:buy_reveal")
async def questions_buy_reveal_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    public_id = data.get("current_question_id")
    row = await db.get_question_by_public_id(public_id)
    if not row or int(row[3]) != callback.from_user.id:
        await callback.answer("Вопрос не найден", show_alert=True)
        return
    if bool(row[10]):
        await _send_question_author(callback.message, int(row[2]))
        await callback.answer()
        return
    invoice_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Оплатить 100 ⭐", pay=True)],
        [InlineKeyboardButton(text="↩️ Передумал", callback_data=f"question_reveal_cancel:{public_id}")],
    ])
    invoice = await callback.bot.send_invoice(
        chat_id=callback.message.chat.id,
        title="Раскрытие автора вопроса",
        description="После оплаты вы увидите Telegram-профиль автора этого анонимного вопроса.",
        payload=f"question_reveal:{public_id}",
        currency="XTR",
        prices=[LabeledPrice(label="Узнать автора", amount=100)],
        reply_markup=invoice_keyboard,
    )
    pending_invoice_message_ids[callback.from_user.id] = invoice.message_id
    await callback.answer()


@router.callback_query(F.data == "questions:show_author")
async def questions_show_author_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    public_id = data.get("current_question_id")
    row = await db.get_question_by_public_id(public_id)
    if not row or int(row[3]) != callback.from_user.id:
        await callback.answer("Вопрос не найден", show_alert=True)
        return
    if not bool(row[10]):
        await callback.answer("Автор ещё не раскрыт", show_alert=True)
        return
    await _send_question_author(callback.message, int(row[2]))
    await callback.answer()


@router.callback_query(F.data == "questions:gift")
async def questions_gift_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    public_id = data.get("current_question_id")
    if not public_id:
        await callback.answer("Вопрос не найден", show_alert=True)
        return
    await _open_question_gift_menu(
        callback.message,
        state,
        context="q",
        reference=str(public_id),
        return_to="question",
    )
    await callback.answer()


@router.callback_query(F.data == "questions:ask_again")
async def questions_ask_again_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    public_id = data.get("current_answer_question_id")
    row = await db.get_question_by_public_id(public_id)
    if not row or int(row[2]) != callback.from_user.id:
        await callback.answer("Ответ не найден", show_alert=True)
        return
    owner = await db.get_question_owner_by_id(int(row[3]))
    display_name = _display_name(owner) if owner else "пользователю"
    await state.set_state(AnonymousQuestionFlow.target_menu)
    await state.update_data(question_target_id=int(row[3]), question_target_name=display_name)
    try:
        await callback.message.edit_text(
            f"Выберите действие для <b>{escape(display_name)}</b>.",
            parse_mode="HTML",
            reply_markup=question_target_inline(display_name),
        )
    except Exception:
        await callback.message.answer(
            f"Выберите действие для <b>{escape(display_name)}</b>.",
            parse_mode="HTML",
            reply_markup=question_target_inline(display_name),
        )
    await callback.answer()


@router.callback_query(F.data == "questions:answer_gift")
async def questions_answer_gift_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    public_id = data.get("current_answer_question_id")
    if not public_id:
        await callback.answer("Ответ не найден", show_alert=True)
        return
    await _open_question_gift_menu(
        callback.message,
        state,
        context="a",
        reference=str(public_id),
        return_to="answer",
    )
    await callback.answer()



@router.callback_query(F.data == "questions:target_home")
async def questions_target_home_callback(callback: CallbackQuery, state: FSMContext):
    await _send_target_screen(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "questions:gift_back")
async def questions_gift_back_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    return_to = data.get("gift_return_to")
    if return_to == "target":
        await _send_target_screen(callback.message, state)
    elif return_to == "question":
        public_id = data.get("current_question_id")
        row = await db.get_question_by_public_id(public_id) if public_id else None
        if row:
            card = _question_card_text(row) if "_question_card_text" in globals() else (
                f"❓ <b>Вопрос №{row[0]}</b>\n\n{escape(row[4] or '')}"
            )
            await state.set_state(AnonymousQuestionFlow.viewing_question)
            await callback.message.answer(card, parse_mode="HTML", reply_markup=question_card_inline(bool(row[10])))
    elif return_to == "answer":
        public_id = data.get("current_answer_question_id")
        row = await db.get_question_by_public_id(public_id) if public_id else None
        if row:
            await state.set_state(AnonymousQuestionFlow.viewing_answer)
            await callback.message.answer(
                f"💬 <b>Ответ на вопрос №{row[0]}</b>\n\n{escape(row[5] or '')}",
                parse_mode="HTML",
                reply_markup=answer_card_inline(),
            )
    await callback.answer()


@router.callback_query(F.data == "questions:gift_regular")
async def questions_gift_regular_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await _show_question_gifts(callback.message, context=str(data.get("gift_context", "")), reference=str(data.get("gift_reference", "")))
    await callback.answer()


@router.callback_query(F.data == "questions:gift_stars")
async def questions_gift_stars_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    context, reference = str(data.get("gift_context", "")), str(data.get("gift_reference", ""))
    await callback.message.answer("⭐ <b>Выберите количество звёзд</b>", parse_mode="HTML", reply_markup=_stars_amount_inline(context, reference))
    await callback.answer()


@router.callback_query(F.data == "questions:gift_vip")
async def questions_gift_vip_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await _send_question_vip_invoice(callback.message, context=str(data.get("gift_context", "")), reference=str(data.get("gift_reference", "")))
    await callback.answer()


@router.callback_query(F.data == "questions:gift_premium")
async def questions_gift_premium_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    context, reference = str(data.get("gift_context", "")), str(data.get("gift_reference", ""))
    await callback.message.answer("💎 <b>Выберите срок Telegram Premium</b>", parse_mode="HTML", reply_markup=_premium_inline(context, reference))
    await callback.answer()


@router.callback_query(F.data == "questions:ask_target")
async def questions_ask_target_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("question_target_id"):
        await callback.answer("Получатель недоступен", show_alert=True)
        return
    await _send_write_question_screen(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "questions:target_gift")
async def questions_target_gift_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    target_id = data.get("question_target_id")
    if not target_id:
        await callback.answer("Получатель недоступен", show_alert=True)
        return
    await _open_question_gift_menu(
        callback.message,
        state,
        context="t",
        reference=str(target_id),
        return_to="target",
    )
    await callback.answer()


@router.callback_query(F.data == "questions:back_mine")
async def questions_back_mine_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    await _questions_page_for_callback(callback, state, int(data.get("question_list_offset", 0)))

@router.callback_query(F.data == "questions:back_answers")
async def questions_back_answers_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    await _answers_page_for_callback(callback, state, int(data.get("answer_list_offset", 0)))

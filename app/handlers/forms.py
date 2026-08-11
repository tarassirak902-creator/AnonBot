from app.core.games import GAME_NAMES
from .shared import *

# =====================================================================
# 2. ВВОД СУММЫ СТАВКИ ДЛЯ ИГР И ВЫВОД СРЕДСТВ
# =====================================================================

@router.message(UserWithdraw.waiting_for_amount)
async def process_withdraw_amount(message: Message, state: FSMContext):
    user_id = message.from_user.id
    text = (message.text or "").strip()
    if not text.isdigit() or int(text) <= 0:
        await message.answer("❌ Введите корректную сумму Звёзд числом:")
        return

    amount = int(text)
    balance = await db.get_user_balance(user_id)

    if amount > balance:
        await message.answer(f"❌ Недостаточно средств на балансе! Ваш баланс в боте: <b>{balance} ⭐</b>", parse_mode="HTML")
        await state.clear()
        return

    req_id = await db.create_withdraw_request_atomic(user_id, amount)
    if req_id is None:
        await message.answer("❌ Баланс уже изменился или средств недостаточно. Обновите профиль и повторите попытку.")
        await state.clear()
        return
    await state.clear()

    await message.answer(
        f"✅ <b>Заявка #{req_id} на вывод {amount} ⭐ создана!</b>\n\n"
        f"Она отправлена на проверку администратору. После одобрения вы получите уведомление.",
        parse_mode="HTML"
    )

    try:
        user = message.from_user
        u_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        u_un = f"@{user.username}" if user.username else "нет"

        admin_text = (
            f"💸 <b>НОВАЯ ЗАЯВКА НА ВЫВОД ЗВЁЗД!</b>\n\n"
            f"🆔 <b>ID Заявки:</b> #{req_id}\n"
            f"👤 <b>Пользователь:</b> {html.escape(u_name)} ({html.escape(u_un)})\n"
            f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
            f"⭐ <b>Сумма вывода:</b> {amount} ⭐"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Одобрить", callback_data=f"withdraw_approve_{req_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"withdraw_reject_{req_id}")
            ]
        ])
        log_message = await message.bot.send_message(LOG_CHANNEL_ID, admin_text, parse_mode="HTML", reply_markup=kb)
        await db.set_withdraw_log_message(req_id, log_message.chat.id, log_message.message_id)
    except Exception:
        logger.exception(
            "Ошибка логирования заявки на вывод: user_id=%s, request_id=%s",
            user_id,
            req_id,
        )

@router.message(GameSoloBet.waiting_for_bet)
async def process_solo_game_bet(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit() or int(text) <= 0:
        await message.answer("❌ Введите целое число для ставки:")
        return

    bet = int(text)
    data = await state.get_data()
    game_type = data.get("game_type", "darts")
    prompt_message_id = data.get("prompt_message_id")
    await state.clear()

    title_name = GAME_NAMES.get(game_type, "Игру")

    pay_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⭐ Оплатить ставку {bet} ⭐", pay=True)],
        [InlineKeyboardButton(text="↩️ Назад к выбору игр", callback_data="solo_result_games")],
    ])
    if prompt_message_id:
        try:
            await message.bot.delete_message(message.chat.id, prompt_message_id)
        except Exception:
            pass
    try:
        await message.delete()
    except Exception:
        pass

    invoice = await message.answer_invoice(
        title=f"Ставка в {title_name}",
        description=f"Оплата ставки {bet} ⭐ для игры против бота.",
        payload=f"solo_{game_type}_{bet}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"Ставка {bet} Звёзд", amount=bet)],
        start_parameter="solo_game",
        reply_markup=pay_kb
    )
    pending_invoice_message_ids[message.from_user.id] = invoice.message_id

@router.message(GameDuelBet.waiting_for_bet)
async def process_duel_game_bet(message: Message, state: FSMContext):
    user_id = message.from_user.id
    partner_info = await db.get_partner(user_id)
    if not partner_info:
        await message.answer("Вы не в диалоге.")
        await state.clear()
        return

    partner_id = partner_info
    text = (message.text or "").strip()
    if not text.isdigit() or int(text) <= 0:
        await message.answer("❌ Введите целое число для ставки:")
        return

    bet = int(text)
    data = await state.get_data()
    game_type = data.get("game_type", "darts")
    await state.clear()

    pay_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"⚔️ Оплатить ставку {bet} ⭐",
                    pay=True,
                )
            ],
            [
                InlineKeyboardButton(
                    text="↩️ Назад",
                    callback_data=f"duel_invoice_back:{game_type}",
                )
            ],
        ]
    )

    await message.answer_invoice(
        title="Создание дуэли",
        description=f"Оплата вашей ставки {bet} ⭐ для вызова собеседника на дуэль.",
        payload=f"duel_create_{partner_id}_{bet}_{game_type}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"Ставка для дуэли: {bet} ⭐", amount=bet)],
        start_parameter="duel_create",
        reply_markup=pay_kb
    )

@router.message(AdminSettings.waiting_for_reveal_cost)
async def process_new_reveal_cost(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    text = (message.text or "").strip()
    if not text.isdigit() or int(text) <= 0:
        await message.answer("❌ Стоимость должна быть целым положительным числом:")
        return

    new_cost = int(text)
    await db.set_setting("reveal_cost", str(new_cost))
    await state.clear()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить стоимость раскрытия", callback_data="admin_change_reveal_cost")]
    ])
    await message.answer(f"✅ <b>Стоимость раскрытия успешно изменена на {new_cost} ⭐!</b>", parse_mode="HTML", reply_markup=kb)

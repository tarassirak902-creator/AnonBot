from .shared import *
from .callbacks_duels import profile_refresh_handler
from app.core.games import GAME_NAMES

# =====================================================================
# 5. ALL CALLBACK QUERIES (ПРОФИЛЬ, ВЫВОД, ИГРЫ, VIP, АДМИНКА)
# =====================================================================

@router.callback_query(F.data == "buy_vip_sub")
async def buy_vip_sub_handler(callback: CallbackQuery):
    await callback.answer()
    pay_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👑 Оплатить 100 ⭐ (VIP на 1 мес.)", pay=True)],
        [InlineKeyboardButton(text="↩️ Назад в профиль", callback_data="profile_back")],
    ])
    await safe_delete_message(callback.message)
    invoice = await callback.message.answer_invoice(
        title="VIP Подписка",
        description="Приобретение VIP статуса на 1 месяц. Включает скидку 30% на все подарки и полную защиту от автоматических предупреждений бота.",
        payload="vip_subscription_100",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="VIP Подписка на 1 месяц", amount=100)],
        start_parameter="vip_sub",
        reply_markup=pay_kb,
    )
    pending_invoice_message_ids[callback.from_user.id] = invoice.message_id

@router.callback_query(F.data == "profile_withdraw")
async def profile_withdraw_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    bal = await db.get_user_balance(user_id)
    if bal <= 0:
        await callback.answer("❌ У вас 0 ⭐ на балансе для вывода!", show_alert=True)
        return
        
    await callback.answer()
    text = (
        f"💸 <b>ВЫВОД ЗВЁЗД TELEGRAM</b>\n"
        f"───────────────\n\n"
        f"⭐ <b>Доступно для вывода:</b> {bal} ⭐\n\n"
        f"Введите сумму Звёзд, которую вы хотите вывести:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ Назад в профиль", callback_data="profile_back")]
    ])
    await safe_delete_message(callback.message)
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await state.set_state(UserWithdraw.waiting_for_amount)

@router.callback_query(F.data == "profile_invited_users")
async def profile_invited_handler(callback: types.CallbackQuery):
    await callback.answer()
    ref_link, _share_url, stats = await prepare_referral_data(
        callback.bot,
        callback.from_user.id,
    )
    text = (
        "👥 <b>ПРИГЛАШЁННЫЕ ПОЛЬЗОВАТЕЛИ</b>\n───────────────\n\n"
        f"🔗 <b>Ваша ссылка:</b>\n<code>{ref_link}</code>\n\n"
        f"👤 Всего приглашено: <b>{stats['total']}</b>\n"
        f"✅ Активных друзей: <b>{stats['active']}</b>\n"
        f"⏳ Набирают активность: <b>{stats['pending']}</b>\n"
        f"🎁 Наград получено: <b>{stats['rewards']}</b>\n"
        f"⭐ Всего начислено: <b>{stats['reward_stars']}</b>\n\n"
        "Друг становится активным после 5 завершённых диалогов."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Подробная статистика", callback_data="referral_stats")],
        [InlineKeyboardButton(text="↩️ Назад в профиль", callback_data="profile_back")],
    ])
    await safe_delete_message(callback.message)
    await send_brand_card(callback.message, "invite", text, kb)

@router.callback_query(F.data == "profile_back")
async def profile_back_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    pending_invoice_message_ids.pop(callback.from_user.id, None)
    await profile_refresh_handler(callback)

@router.callback_query(F.data.startswith("admin_cancel_vip_"))
async def admin_cancel_vip_handler(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    target_id = int(callback.data.split("_")[3])
    await db.set_user_vip(target_id, False)
    await db.log_action(target_id, "admin:vip_removed", f"admin_id={callback.from_user.id}")
    await callback.answer("VIP подписка пользователя аннулирована!", show_alert=True)
    try:
        await callback.bot.send_message(
            target_id,
            "ℹ️ Ваша VIP подписка была отменена администратором.",
        )
    except Exception as exc:
        await db.log_action(
            callback.from_user.id,
            "admin_vip_remove_notify_error",
            f"target_id={target_id}; error={exc}",
        )
    await refresh_admin_user_message(callback.message, target_id, "✅ VIP-подписка снята")

@router.callback_query(F.data.startswith("admin_give_vip_"))
async def admin_give_vip_handler(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    target_id = int(callback.data.split("_")[3])
    await db.extend_user_vip_days(target_id, days=30)
    await db.log_action(target_id, "admin:vip_granted", f"admin_id={callback.from_user.id}; days=30")
    await callback.answer("VIP подписка успешно выдана на 30 дней!", show_alert=True)
    try:
        await callback.bot.send_message(
            target_id,
            "👑 <b>Администратор выдал вам VIP подписку на 30 дней!</b>",
            parse_mode="HTML",
        )
    except Exception as exc:
        await db.log_action(
            callback.from_user.id,
            "admin_vip_give_notify_error",
            f"target_id={target_id}; error={exc}",
        )
    await refresh_admin_user_message(callback.message, target_id, "✅ VIP-подписка выдана на 30 дней")

# --- СОЛО ИГРЫ С БОТОМ ---
@router.callback_query(F.data.startswith("game_solo_"))
async def start_solo_game_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    game_type = callback.data.split("_")[2]
    game_title = GAME_NAMES.get(game_type, "Игру")
    text = (
        f"<b>{game_title} (против Бота)</b>\n───────────────\n\n"
        f"Введите сумму вашей ставки в Звёздах:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ Назад к выбору игр", callback_data="solo_games_back")]
    ])
    await safe_delete_message(callback.message)
    prompt = await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await state.update_data(game_type=game_type, prompt_message_id=prompt.message_id)
    await state.set_state(GameSoloBet.waiting_for_bet)

@router.callback_query(F.data == "solo_games_close")
async def solo_games_close_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    await safe_delete_message(callback.message)
    await show_main_menu_screen(callback.message, callback.from_user.id)


@router.callback_query(F.data == "solo_games_back")
async def solo_games_back_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    await safe_delete_message(callback.message)
    await show_games_screen(callback.message)

@router.callback_query(F.data.startswith("solo_replay_"))
async def solo_replay_handler(callback: CallbackQuery):
    await callback.answer()
    _, _, game_type, bet_raw = callback.data.split("_", 3)
    bet = int(bet_raw)
    game_title = GAME_NAMES.get(game_type, "Мини-игра")
    await safe_delete_message(callback.message)
    pay_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⭐ Оплатить ставку {bet} ⭐", pay=True)],
        [InlineKeyboardButton(text="↩️ Назад к выбору игр", callback_data="solo_result_games")],
    ])
    invoice = await callback.message.answer_invoice(
        title=f"Ставка в {game_title}",
        description=f"Оплата ставки {bet} ⭐ для игры против бота.",
        payload=f"solo_{game_type}_{bet}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"Ставка {bet} Звёзд", amount=bet)],
        start_parameter="solo_game",
        reply_markup=pay_kb,
    )
    pending_invoice_message_ids[callback.from_user.id] = invoice.message_id


@router.callback_query(F.data == "solo_result_games")
async def solo_result_games_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    pending_invoice_message_ids.pop(callback.from_user.id, None)
    await safe_delete_message(callback.message)
    await show_games_screen(callback.message)


@router.callback_query(F.data == "duel_games_close")
async def duel_games_close_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    await safe_delete_message(callback.message)
    # Дуэли открываются из активного диалога, поэтому возвращаем панель диалога.
    await callback.message.answer(
        "💬 <b>Вы вернулись в диалог.</b>",
        parse_mode="HTML",
        reply_markup=chat_menu(),
    )


# --- ДУЭЛИ С СОБЕСЕДНИКОМ ---
@router.callback_query(F.data.startswith("game_duel_"))
async def start_duel_game_handler(callback: CallbackQuery, state: FSMContext):
    if not await db.get_partner(callback.from_user.id):
        await callback.answer("Дуэли доступны только во время активного диалога.", show_alert=True)
        return
    await callback.answer()
    game_type = callback.data.split("_")[2]

    game_title = GAME_NAMES.get(game_type, "Дуэль")

    text = (
        f"⚔️ <b>{game_title} с собеседником</b>\n───────────────\n\n"
        f"Победитель забирает весь банк себе\n"
        f"Введите сумму ставки для дуэли в Звёздах:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ Назад к выбору дуэлей", callback_data="duel_games_back")]
    ])
    await safe_delete_message(callback.message)
    prompt = await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)

    await state.update_data(game_type=game_type, prompt_message_id=prompt.message_id)
    await state.set_state(GameDuelBet.waiting_for_bet)

@router.callback_query(F.data.startswith("duel_invoice_back:"))
async def duel_invoice_back_handler(
    callback: CallbackQuery,
    state: FSMContext,
):
    user_id = callback.from_user.id
    partner_id = await db.get_partner(user_id)

    if not partner_id:
        await state.clear()
        await callback.answer(
            "Диалог уже завершён.",
            show_alert=True,
        )
        await safe_delete_message(callback.message)
        await callback.message.answer(
            "👻 Диалог уже завершён.",
            reply_markup=main_menu(user_id in ADMIN_IDS),
        )
        return

    game_type = callback.data.split(":", 1)[1]
    game_title = GAME_NAMES.get(game_type, "Дуэль")

    await callback.answer()
    await safe_delete_message(callback.message)

    text = (
        f"⚔️ <b>{game_title} с собеседником</b>\n"
        "───────────────\n\n"
        "Победитель забирает весь банк себе\n"
        "Введите сумму ставки для дуэли в Звёздах:"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="↩️ Назад к выбору дуэлей",
                    callback_data="duel_games_back",
                )
            ]
        ]
    )

    prompt = await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=keyboard,
    )

    await state.update_data(
        game_type=game_type,
        prompt_message_id=prompt.message_id,
    )
    await state.set_state(GameDuelBet.waiting_for_bet)


@router.callback_query(F.data == "duel_games_back")
async def duel_games_back_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    await safe_delete_message(callback.message)
    await callback.message.answer(
        "⚔️ <b>Выберите режим дуэли с собеседником:</b>",
        parse_mode="HTML",
        reply_markup=duel_games_menu_kb(),
    )


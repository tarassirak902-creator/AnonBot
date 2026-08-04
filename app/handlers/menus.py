from .shared import *
from .casper_game import MAX_ATTEMPTS_PER_SEARCH, open_casper_board

# =====================================================================
# 4. ТЕКСТОВЫЕ КНОПКИ МЕНЮ И ПРОФИЛЬ
# =====================================================================

from .profile_view import send_profile_screen

@router.message(F.text.in_({"⚙️ Профиль", "👤 Моя анкета", "👤 Профиль"}))
async def profile(message: Message, state: FSMContext):
    await state.clear()
    await hide_reply_keyboard(message)
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        u = message.from_user
        await db.add_user(u.id, u.username, u.first_name, u.last_name)
    await send_profile_screen(message, user_id)

@router.message(F.text.in_({"Мини игры", "🎮 Мини-игры", "🎮 Игры"}))
async def solo_games_start_menu(message: Message, state: FSMContext):
    await state.clear()
    await hide_reply_keyboard(message)
    await send_brand_card(
        message,
        "games",
        "🎮 <b>Игровая зона</b>\n\nВыберите игру и попробуйте заработать ⭐.",
        solo_games_menu_kb(),
    )

@router.message(F.text == "⚔️ Играть с собеседником")
async def duel_games_start_menu(message: Message, state: FSMContext):
    await state.clear()
    if not await db.get_partner(message.from_user.id):
        await message.answer("Дуэли доступны только во время активного диалога.")
        return
    await message.answer("⚔️ <b>Выберите режим дуэли с собеседником:</b>", parse_mode="HTML", reply_markup=duel_games_menu_kb())

@router.message(F.text == "👻 Поймать CASPER")
async def search_casper_game(message: Message):
    """Запускает один раунд игры во время поиска собеседника."""
    user_id = message.from_user.id

    if await db.get_partner(user_id):
        await message.answer(
            "💬 Собеседник уже найден — игра завершена.",
            reply_markup=chat_menu(),
        )
        return

    if not await db.is_in_queue(user_id):
        await message.answer(
            "👻 Играть здесь можно только во время поиска собеседника.",
            reply_markup=main_menu(user_id in ADMIN_IDS),
        )
        return

    attempts = search_game_attempts.get(user_id, 0)

    if attempts >= MAX_ATTEMPTS_PER_SEARCH:
        await message.answer(
            (
    f"⏳ Вы использовали все "
    f"{MAX_ATTEMPTS_PER_SEARCH} попыток этого поиска.\n\n"
    "CASPER продолжает искать вам собеседника."
),
            reply_markup=cancel_search_menu(),
        )
        return

    now = time.monotonic()
    last_spin = search_game_last_spin.get(user_id, 0.0)
    cooldown_left = 3.0 - (now - last_spin)

    if cooldown_left > 0:
        await message.answer(
            f"⏳ Подождите ещё {max(1, int(cooldown_left + 0.9))} сек."
        )
        return

    search_game_last_spin[user_id] = now
    attempts += 1
    search_game_attempts[user_id] = attempts

    await open_casper_board(
        message=message,
        attempt_no=attempts,
    )


@router.message(F.text.in_({"💬 Найти собеседника", "🚀 Начать общение"}))
async def search_start(message: Message, state: FSMContext):
    await state.clear()
    await start_searching(message)

@router.message(F.text == "❌  Отменить поиск")
async def cancel_search_handler(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    cancel_search_timer(user_id)
    await delete_search_card(message.bot, user_id)
    await db.remove_from_queue(user_id)
    await db.log_action(user_id, "queue_leave", "user_cancelled")
    await send_brand_card(
        message,
        "search_cancelled",
        "👻 <b>CASPER</b>\n\nПоиск остановлен.",
        main_menu(user_id in ADMIN_IDS),
    )

@router.message(F.text == "➡️ Следующий собеседник")
async def next_partner(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    cancel_search_timer(user_id)
    
    await db.add_completed_chat_time(user_id)
    partner_id = await db.end_chat(user_id)
    if partner_id: await db.add_completed_chat_time(partner_id)
    cancel_inactivity_timer(user_id, partner_id)
    cancel_unread_reminder(user_id)
    if partner_id: cancel_unread_reminder(partner_id)

    if partner_id:
        try:
            await message.bot.send_message(partner_id, "Собеседник завершил диалог.", reply_markup=main_menu(partner_id in ADMIN_IDS))
            await message.answer("Вы завершили диалог. Ищем нового собеседника...")
            from .advertising import send_ads_to_dialog_users
            await send_ads_to_dialog_users(message.bot, user_id, partner_id, f"manual:{min(user_id, partner_id)}:{max(user_id, partner_id)}:{int(datetime.now().timestamp())}")
            await message.bot.send_message(partner_id, "Хотите узнать, с кем вы только что общались?", reply_markup=reveal_offer_kb(user_id))
            await message.answer("Хотите узнать, кто это был?", reply_markup=reveal_offer_kb(partner_id))
        except Exception:
            pass
        await start_searching(message)
    else:
        await db.remove_from_queue(user_id)
        await message.answer("Старый диалог уже был завершён. Ищем нового собеседника...")
        await start_searching(message)

@router.message(F.text == "❌ Завершить диалог")
async def end_dialog(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    cancel_search_timer(user_id)
    
    await db.add_completed_chat_time(user_id)
    partner_id = await db.end_chat(user_id)
    if partner_id: await db.add_completed_chat_time(partner_id)
    cancel_inactivity_timer(user_id, partner_id)
    cancel_unread_reminder(user_id)
    if partner_id: cancel_unread_reminder(partner_id)

    if partner_id:
        try:
            await message.bot.send_message(partner_id, "Собеседник завершил общение.", reply_markup=main_menu(partner_id in ADMIN_IDS))
            await send_brand_card(
                message,
                "dialog_ended",
                "👻 <b>CASPER</b>\n\nДиалог завершён.",
                main_menu(user_id in ADMIN_IDS),
            )
            from .advertising import send_ads_to_dialog_users
            await send_ads_to_dialog_users(message.bot, user_id, partner_id, f"manual:{min(user_id, partner_id)}:{max(user_id, partner_id)}:{int(datetime.now().timestamp())}")
            await message.bot.send_message(partner_id, "Хотите узнать, с кем вы только что общались?", reply_markup=reveal_offer_kb(user_id))
            await message.answer("Хотите узнать, кто был вашим собеседником?", reply_markup=reveal_offer_kb(partner_id))
        except Exception:
            pass
        await db.log_action(user_id, "dialog_end", f"with {partner_id}")
    else:
        await message.answer("Вы не находитесь в диалоге.")

@router.message(F.text == "🎁 Подарить подарок")
async def show_gifts(message: Message, skip_dialog_check: bool = False):
    user_id = message.from_user.id
    if not skip_dialog_check and not await db.get_partner(user_id):
        await message.answer("Вы не находитесь в диалоге.")
        return
        
    gifts = await db.get_all_gifts()
    if not gifts:
        await message.answer("Нет доступных подарков.")
        return
    
    is_vip = await db.is_user_vip(user_id)

    keyboard, row = [], []
    for g in gifts:
        gid, name, emoji, price = g
        actual_price = int(price * 0.7) if is_vip else price
        price_text = f"{actual_price} ⭐ (-30%)" if is_vip else f"{price} ⭐"
        
        button = InlineKeyboardButton(text=f"{emoji} {name} — {price_text}", callback_data=f"buy_gift_{gid}")
        row.append(button)
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton(text="не заслужила😜", callback_data="close_gifts_menu")])
        
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer("🎁 Выберите подарок для собеседника:", reply_markup=kb)

@router.message(F.text == "⭐ Кто собеседник")
async def reveal_partner(message: Message):
    user_id = message.from_user.id
    partner_info = await db.get_partner(user_id)
    if not partner_info:
        await message.answer("Вы не находитесь в диалоге.")
        return
    cost = int(await db.get_setting("reveal_cost"))

    pay_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Узнать за {cost} ⭐ ", pay=True)],
        [InlineKeyboardButton(
            text="↩️ Назад в диалог",
            callback_data="reveal_back_to_chat",
        )],
    ])

    await message.answer_invoice(
        title="Узнать собеседника",
        description="Раскрыть имя, username и Telegram ID собеседника.",
        payload=f"reveal_{partner_info}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Раскрытие личности", amount=cost)],
        start_parameter="reveal",
        reply_markup=pay_kb
    )

@router.message(F.text == "⚠️ Пожаловаться")
async def complaint_menu(message: Message):
    if not await db.get_partner(message.from_user.id):
        await message.answer("Вы не в диалоге.")
        return
    await message.answer("Выберите причину жалобы:", reply_markup=complaint_reasons())

@router.message(F.text.in_({"🔧 Админ-панель", "⚙️ Админ-панель CASPER", "⚙️ Панель управления"}))
async def admin_panel_menu(message: Message):

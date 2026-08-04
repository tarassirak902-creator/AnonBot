from .shared import *
from .casper_game import MAX_ATTEMPTS_PER_SEARCH, open_casper_board

# =====================================================================
# 4. ТЕКСТОВЫЕ КНОПКИ МЕНЮ И ПРОФИЛЬ
# =====================================================================

from .profile_view import send_profile_screen

@router.message(F.text.in_({"⚙️ Профиль", "👤 Моя анкета"}))
async def profile(message: Message, state: FSMContext):
    await state.clear()
    await hide_reply_keyboard(message)
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        u = message.from_user
        await db.add_user(u.id, u.username, u.first_name, u.last_name)
    await send_profile_screen(message, user_id)

@router.message(F.text.in_({"Мини игры", "🎮 Мини-игры"}))
async def solo_games_start_menu(message: Message, state: FSMContext):
    await state.clear()
    await hide_reply_keyboard(message)
    await send_brand_card(
        message,
        "games",
        "🎮 <b>Мини-игры CASPER</b>\n\nВыберите одиночную игру против CASPER на ⭐ Звёзды:",
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


@router.message(F.text == "💬 Найти собеседника")
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

@router.message(F.text.in_({"🔧 Админ-панель", "⚙️ Админ-панель CASPER"}))
async def admin_panel_menu(message: Message):
    if message.from_user.id not in ADMIN_IDS: return
    await send_brand_card(
        message,
        "admin",
        "⚙️ <b>Панель управления CASPER</b>\n\nУправление пользователями, рекламой, статистикой и настройками бота.",
        admin_panel(),
    )

def admin_users_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Поиск пользователя", callback_data="admin_user_search")],
        [InlineKeyboardButton(text="⚠️ Пользователи с предупреждениями", callback_data="admin_warned_list")],
        [InlineKeyboardButton(text="🔒 Ограниченные пользователи", callback_data="admin_restricted_list")],
        [InlineKeyboardButton(text="📥 Скачать базу пользователей (.xlsx)", callback_data="admin_download_users")],
        [InlineKeyboardButton(text="↩️ Назад в админ-панель", callback_data="admin_back_to_panel")],
    ])

@router.message(F.text.in_({"📊 Статистика", "📊 Статистика и пользователи", "👥 Пользователи"}))
async def admin_stats(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    await state.clear()
    s = await db.get_statistics()
    text = (
        "📊 <b>Статистика и пользователи</b>\n\n"
        "👥 <b>Пользователи</b>\n"
        f"├ Всего: <b>{s['total_users']}</b>\n"
        f"├ Новых за сегодня: <b>{s['new_today']}</b>\n"
        f"├ Активных VIP: <b>{s['active_vip_users']}</b>\n"
        f"└ Куплено VIP-подписок: <b>{s['vip_purchases']}</b>\n\n"
        "💬 <b>Общение</b>\n"
        f"├ В очереди: <b>{s['queue_count']}</b>\n"
        f"└ Активных диалогов: <b>{s['active_chats']}</b>\n\n"
        "🎁 <b>Активность и платежи</b>\n"
        f"├ Отправлено подарков: <b>{s['total_gifts_sent']}</b>\n"
        f"├ Подарков за сутки: <b>{s['gifts_today']}</b>\n"
        f"├ Получено звёзд: <b>{s['total_stars']}</b>\n"
        f"├ Раскрытий: <b>{s['reveal_count']}</b>\n"
        f"└ Жалоб: <b>{s['total_complaints']}</b>\n\n"
        "Выберите действие с пользователями:"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=admin_users_menu_kb())

@router.message(F.text == "💸 Заявки на вывод")
async def admin_withdraw_requests(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    rows = await db.get_pending_withdraw_requests()
    if not rows:
        await message.answer("💸 <b>Заявок на вывод нет.</b>", parse_mode="HTML")
        return
    await message.answer(
        f"💸 <b>Заявки на вывод</b>\n\nОжидают обработки: <b>{len(rows)}</b>",
        parse_mode="HTML",
    )
    for req_id, uid, amount, created_at, username, first_name, last_name in rows:
        full_name = " ".join(x for x in (first_name, last_name) if x).strip() or "не указано"
        uname = f"@{username}" if username else "нет"
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"withdraw_approve_{req_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"withdraw_reject_{req_id}"),
        ]])
        await message.answer(
            f"💸 <b>Заявка #{req_id}</b>\n\n"
            f"👤 Пользователь: <b>{full_name}</b> ({uname})\n"
            f"🆔 ID: <code>{uid}</code>\n"
            f"⭐ Сумма: <b>{amount} ⭐</b>\n"
            f"🕒 Создана: <code>{created_at}</code>",
            parse_mode="HTML",
            reply_markup=kb,
        )


@router.message(F.text == "📨 Рассылка")
async def broadcast_start(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="↩️ Назад", callback_data="admin_back_to_panel")]])
    await message.answer("Отправьте сообщение для рассылки (текст, фото, видео, голосовое и т.д.):", reply_markup=kb)
    await state.set_state(Broadcast.waiting_for_message)


def broadcast_preview_kb(button_text=None, button_url=None):
    rows = []
    if button_text and button_url:
        rows.append([InlineKeyboardButton(text=button_text, url=button_url)])
    rows.extend([
        [InlineKeyboardButton(text="✏️ Добавить текст", callback_data="broadcast_add_text")],
        [InlineKeyboardButton(text="➕ Добавить URL-кнопку", callback_data="broadcast_add_button")],
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_broadcast"), InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_broadcast")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="admin_back_to_panel")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def show_broadcast_preview(target, state: FSMContext):
    data = await state.get_data()
    chat_id, msg_id = data.get("chat_id"), data.get("msg_id")
    extra_text = data.get("extra_text")
    button_text, button_url = data.get("button_text"), data.get("button_url")
    await target.answer("👁 <b>Предпросмотр рассылки:</b>", parse_mode="HTML")
    if chat_id and msg_id:
        await target.bot.copy_message(target.chat.id, chat_id, msg_id)
    if extra_text:
        await target.answer(extra_text, parse_mode="HTML")
    await target.answer("Настройте рассылку или подтвердите отправку.", reply_markup=broadcast_preview_kb(button_text, button_url))
    await state.set_state(Broadcast.waiting_for_confirmation)


@router.message(Broadcast.waiting_for_message)
async def broadcast_receive_message(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear(); return
    await state.update_data(msg_id=message.message_id, chat_id=message.chat.id, button_text=None, button_url=None, extra_text=None)
    await show_broadcast_preview(message, state)


@router.callback_query(Broadcast.waiting_for_confirmation, F.data == "broadcast_add_text")
async def broadcast_add_text(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await callback.answer()
    await callback.message.edit_text(
        "✏️ Отправьте дополнительный текст для рассылки:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="↩️ Назад к предпросмотру", callback_data="broadcast_back_preview")]])
    )
    await state.set_state(Broadcast.waiting_for_text)


@router.message(Broadcast.waiting_for_text)
async def broadcast_receive_text(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear(); return
    text = (message.html_text or message.text or "").strip()
    if not text:
        await message.answer("❌ Отправьте непустой текст.")
        return
    await state.update_data(extra_text=text)
    await show_broadcast_preview(message, state)


@router.callback_query(StateFilter(Broadcast.waiting_for_button, Broadcast.waiting_for_text), F.data == "broadcast_back_preview")
async def broadcast_back_preview(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await callback.answer()
    await safe_delete_message(callback.message)
    await show_broadcast_preview(callback.message, state)


@router.callback_query(Broadcast.waiting_for_confirmation, F.data == "broadcast_add_button")
async def broadcast_add_button(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await callback.answer()
    await callback.message.edit_text(
        "Отправьте кнопку в формате: <code>Текст | https://example.com</code>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="↩️ Назад к предпросмотру", callback_data="broadcast_back_preview")]])
    )
    await state.set_state(Broadcast.waiting_for_button)


@router.message(Broadcast.waiting_for_button)
async def broadcast_receive_button(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear(); return
    parts = (message.text or "").split("|", 1)
    if len(parts) != 2 or not parts[1].strip().startswith(("https://", "http://", "tg://")):
        await message.answer("❌ Формат неверный. Пример: <code>Сайт | https://example.com</code>", parse_mode="HTML"); return
    text, url = parts[0].strip(), parts[1].strip()
    if not text or len(text) > 64:
        await message.answer("❌ Текст кнопки должен содержать от 1 до 64 символов."); return
    await state.update_data(button_text=text, button_url=url)
    await show_broadcast_preview(message, state)


async def banned_words_screen(message):
    words = await db.get_banned_words()
    text = "🚫 <b>Запрещённые слова</b>\n\n" + ("\n".join(f"• {w}" for w in words) if words else "Список пуст.")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить слово", callback_data="admin_word_add")],
        [InlineKeyboardButton(text="➖ Удалить слово", callback_data="admin_word_delete_menu")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="admin_back_to_panel")],
    ])
    await message.answer(text, parse_mode="HTML", reply_markup=kb)

@router.message(F.text == "🚫 Запрещённые слова")
async def banned_words(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    await state.clear(); await banned_words_screen(message)

@router.callback_query(F.data == "admin_word_add")
async def admin_word_add(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await callback.answer(); await state.set_state(BannedWordAdd.waiting_for_word)
    await callback.message.edit_text("➕ Отправьте запрещённое слово или фразу:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="↩️ Назад", callback_data="admin_words_menu")]]))

@router.message(BannedWordAdd.waiting_for_word)
async def admin_word_add_receive(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    word=(message.text or "").strip()
    if not word or len(word)>100:
        await message.answer("❌ Введите слово или фразу длиной до 100 символов."); return
    await db.add_banned_word(word); await state.clear()
    await message.answer(f"✅ Добавлено: <b>{word}</b>", parse_mode="HTML")
    await banned_words_screen(message)

@router.callback_query(F.data.in_({"admin_words_menu", "admin_word_delete_menu"}))
async def admin_words_callbacks(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await state.clear(); await callback.answer()
    words=await db.get_banned_words()
    if callback.data == "admin_word_delete_menu":
        rows=[[InlineKeyboardButton(text=f"❌ {w}", callback_data=f"admin_word_delete:{i}")] for i,w in enumerate(words)]
        rows.append([InlineKeyboardButton(text="↩️ Назад", callback_data="admin_words_menu")])
        await state.update_data(word_delete_list=words)
        await callback.message.edit_text("Выберите слово для удаления:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)); return
    text="🚫 <b>Запрещённые слова</b>\n\n"+("\n".join(f"• {w}" for w in words) if words else "Список пуст.")
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ Добавить слово", callback_data="admin_word_add")],[InlineKeyboardButton(text="➖ Удалить слово", callback_data="admin_word_delete_menu")],[InlineKeyboardButton(text="↩️ Назад", callback_data="admin_back_to_panel")]])
    await safe_delete_message(callback.message)
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data.startswith("admin_word_delete:"))
async def admin_word_delete(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    data=await state.get_data(); words=data.get("word_delete_list", [])
    try:
        word_index = int(callback.data.split(":", 1)[1])
        word = words[word_index]
    except (ValueError, IndexError):
        await callback.answer(
            "Список устарел",
            show_alert=True,
        )
        return
    await db.remove_banned_word(word); await callback.answer(f"Удалено: {word}", show_alert=True)
    remaining=await db.get_banned_words(); await state.update_data(word_delete_list=remaining)
    rows=[[InlineKeyboardButton(text=f"❌ {w}", callback_data=f"admin_word_delete:{i}")] for i,w in enumerate(remaining)]
    rows.append([InlineKeyboardButton(text="↩️ Назад", callback_data="admin_words_menu")])
    await callback.message.edit_text("Выберите слово для удаления:" if remaining else "Список запрещённых слов пуст.", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

async def gifts_admin_screen(message):
    gifts=await db.get_all_gifts()
    text="🎁 <b>Управление подарками</b>\n\n"+("\n".join(f"• {g[2]} {g[1]} — {g[3]} ⭐ (ID {g[0]})" for g in gifts) if gifts else "Подарков нет.")
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ Добавить подарок", callback_data="admin_gift_add")],[InlineKeyboardButton(text="🗑 Выбрать подарки для удаления", callback_data="admin_gift_delete_menu")],[InlineKeyboardButton(text="↩️ Назад", callback_data="admin_back_to_panel")]])
    await message.answer(text, parse_mode="HTML", reply_markup=kb)

@router.message(F.text == "🎁 Управление подарками")
async def gifts_management(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    await state.clear(); await gifts_admin_screen(message)

@router.callback_query(F.data == "admin_gift_add")
async def admin_gift_add(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await callback.answer(); await state.set_state(GiftAdd.waiting_for_name)
    await callback.message.edit_text("Введите подарок в формате:\n<code>Название Эмодзи Цена</code>\nПример: <code>Роза 🌹 25</code>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="↩️ Назад", callback_data="admin_gifts_menu")]]))

@router.message(GiftAdd.waiting_for_name)
async def admin_gift_add_receive(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    parts=(message.text or "").rsplit(maxsplit=2)
    if len(parts)!=3 or not parts[2].isdigit() or int(parts[2])<=0:
        await message.answer("❌ Формат: Название Эмодзи Цена. Например: Роза 🌹 25"); return
    name, emoji, price=parts[0].strip(),parts[1].strip(),int(parts[2])
    await db.add_gift(name,emoji,price); await state.clear()
    await message.answer(f"✅ Добавлен подарок: {emoji} {name} — {price} ⭐")
    await gifts_admin_screen(message)

async def gift_delete_keyboard(selected):
    gifts=await db.get_all_gifts(); rows=[]
    for g in gifts:
        mark="✅" if g[0] in selected else "⬜"
        rows.append([InlineKeyboardButton(text=f"{mark} {g[2]} {g[1]} — {g[3]} ⭐", callback_data=f"admin_gift_toggle_{g[0]}")])
    rows.append([InlineKeyboardButton(text=f"🗑 Удалить выбранные ({len(selected)})", callback_data="admin_gift_delete_confirm")])
    rows.append([InlineKeyboardButton(text="↩️ Назад", callback_data="admin_gifts_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

@router.callback_query(F.data == "admin_gift_delete_menu")
async def admin_gift_delete_menu(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await callback.answer(); await state.set_state(GiftDeleteSelect.selecting); await state.update_data(selected_gifts=[])
    await callback.message.edit_text("Отметьте один или несколько подарков:", reply_markup=await gift_delete_keyboard(set()))

@router.callback_query(F.data.startswith("admin_gift_toggle_"))
async def admin_gift_toggle(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    gid=int(callback.data.rsplit("_",1)[1]); data=await state.get_data(); selected=set(data.get("selected_gifts",[]))
    selected.remove(gid) if gid in selected else selected.add(gid)
    await state.update_data(selected_gifts=list(selected)); await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=await gift_delete_keyboard(selected))

@router.callback_query(F.data == "admin_gift_delete_confirm")
async def admin_gift_delete_confirm(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    selected=set((await state.get_data()).get("selected_gifts",[]))
    if not selected: await callback.answer("Сначала выберите подарки", show_alert=True); return
    for gid in selected: await db.delete_gift(gid)
    await state.clear(); await callback.answer(f"Удалено подарков: {len(selected)}", show_alert=True)
    gifts=await db.get_all_gifts(); text="🎁 <b>Управление подарками</b>\n\n"+("\n".join(f"• {g[2]} {g[1]} — {g[3]} ⭐" for g in gifts) if gifts else "Подарков нет.")
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ Добавить подарок", callback_data="admin_gift_add")],[InlineKeyboardButton(text="🗑 Выбрать подарки для удаления", callback_data="admin_gift_delete_menu")],[InlineKeyboardButton(text="↩️ Назад", callback_data="admin_back_to_panel")]])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data == "admin_gifts_menu")
async def admin_gifts_menu_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await state.clear(); await callback.answer(); gifts=await db.get_all_gifts()
    text="🎁 <b>Управление подарками</b>\n\n"+("\n".join(f"• {g[2]} {g[1]} — {g[3]} ⭐" for g in gifts) if gifts else "Подарков нет.")
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ Добавить подарок", callback_data="admin_gift_add")],[InlineKeyboardButton(text="🗑 Выбрать подарки для удаления", callback_data="admin_gift_delete_menu")],[InlineKeyboardButton(text="↩️ Назад", callback_data="admin_back_to_panel")]])
    await safe_delete_message(callback.message)
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)

@router.message(UserSearch.waiting_for_query)
async def search_user(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    query=(message.text or "").strip().lstrip("@")
    async with aiosqlite.connect(db.DB_PATH) as connection:
        if query.isdigit(): cursor=await connection.execute("SELECT * FROM users WHERE user_id=?",(int(query),))
        else: cursor=await connection.execute("SELECT * FROM users WHERE LOWER(username)=LOWER(?)",(query,))
        user=await cursor.fetchone()
    await state.clear()
    if not user:
        await message.answer("❌ Пользователь не найден.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="↩️ Назад", callback_data="admin_back_to_users")]])); return
    text,kb=admin_user_card(user); await message.answer(text,parse_mode="HTML",reply_markup=kb)

@router.message(F.text == "⚙️ Настройки")
async def settings_menu(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    await state.clear()
    cost = await db.get_setting("reveal_cost") or "15"
    post_price = await db.get_setting("ad_post_package_price_stars") or "150"
    subscriber_price = await db.get_setting("ad_subscriber_package_price_stars") or "100"
    post_min = await db.get_setting("ad_post_min_quantity") or "100"
    subscriber_min = await db.get_setting("ad_subscriber_min_quantity") or "50"
    text = (f"⚙️ <b>Настройки стоимости и рекламы</b>\n\n"
            f"👤 Стоимость раскрытия: {cost} ⭐\n"
            f"📢 Цена показов: {post_price} ⭐\n"
            f"🔒 Цена подписчиков: {subscriber_price} ⭐\n\n"
            f"📉 Минимум показов: {post_min}\n"
            f"📉 Минимум подписчиков: {subscriber_min}")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Стоимость раскрытия", callback_data="admin_change_reveal_cost")],
        [InlineKeyboardButton(text="📢 Цена показов", callback_data="adset_ad_post_package_price_stars")],
        [InlineKeyboardButton(text="🔒 Цена подписчиков", callback_data="adset_ad_subscriber_package_price_stars")],
        [InlineKeyboardButton(text="📉 Минимум показов", callback_data="adset_ad_post_min_quantity")],
        [InlineKeyboardButton(text="📉 Минимум подписчиков", callback_data="adset_ad_subscriber_min_quantity")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="admin_back_to_panel")],
    ])
    await message.answer(text, parse_mode="HTML", reply_markup=kb)

@router.message(F.text == "📋 Логи")
async def view_logs(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👁 Все записи", callback_data="admin_logs_view")],
        [
            InlineKeyboardButton(text="⚠️ Ошибки", callback_data="admin_logs_filter_errors"),
            InlineKeyboardButton(text="🛡 Админы", callback_data="admin_logs_filter_admins"),
        ],
        [
            InlineKeyboardButton(text="💰 Платежи", callback_data="admin_logs_filter_payments"),
            InlineKeyboardButton(text="🚨 Жалобы", callback_data="admin_logs_filter_complaints"),
        ],
        [InlineKeyboardButton(text="📥 Скачать лог .txt", callback_data="admin_logs_download")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="admin_back_to_panel")],
    ])
    await message.answer("📋 <b>Логи бота</b>\n\nВыберите действие:", parse_mode="HTML", reply_markup=kb)


# ===== Входы из новой inline-админки =====
@router.callback_query(F.data == "admin_open_stats")
async def admin_open_stats_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    await callback.answer()
    stats = await db.get_statistics()
    text = (
        "📊 <b>Статистика и пользователи</b>\n\n"
        "👥 <b>Пользователи</b>\n"
        f"├ Всего: <b>{stats['total_users']}</b>\n"
        f"├ Новых за сегодня: <b>{stats['new_today']}</b>\n"
        f"├ Активных VIP: <b>{stats['active_vip_users']}</b>\n"
        f"└ Куплено VIP-подписок: <b>{stats['vip_purchases']}</b>\n\n"
        "💬 <b>Общение</b>\n"
        f"├ В очереди: <b>{stats['queue_count']}</b>\n"
        f"└ Активных диалогов: <b>{stats['active_chats']}</b>\n\n"
        "🎁 <b>Активность и платежи</b>\n"
        f"├ Отправлено подарков: <b>{stats['total_gifts_sent']}</b>\n"
        f"├ Подарков за сутки: <b>{stats['gifts_today']}</b>\n"
        f"├ Получено звёзд: <b>{stats['total_stars']}</b>\n"
        f"├ Раскрытий: <b>{stats['reveal_count']}</b>\n"
        f"└ Жалоб: <b>{stats['total_complaints']}</b>"
    )
    await safe_delete_message(callback.message)
    await callback.message.answer(text, parse_mode="HTML", reply_markup=admin_users_menu_kb())

@router.callback_query(F.data == "admin_open_broadcast")
async def admin_open_broadcast_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    await state.set_state(Broadcast.waiting_for_message)
    await callback.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="↩️ Назад", callback_data="admin_back_to_panel")
    ]])
    await safe_delete_message(callback.message)
    await callback.message.answer(
        "Отправьте сообщение для рассылки (текст, фото, видео, голосовое и т.д.):",
        reply_markup=kb,
    )

@router.callback_query(F.data == "admin_open_settings")
async def admin_open_settings_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    await callback.answer()
    cost = await db.get_setting("reveal_cost") or "15"
    post_price = await db.get_setting("ad_post_package_price_stars") or "150"
    subscriber_price = await db.get_setting("ad_subscriber_package_price_stars") or "100"
    post_min = await db.get_setting("ad_post_min_quantity") or "100"
    subscriber_min = await db.get_setting("ad_subscriber_min_quantity") or "50"
    text = (
        f"⚙️ <b>Настройки стоимости и рекламы</b>\n\n"
        f"👤 Стоимость раскрытия: {cost} ⭐\n"
        f"📢 Цена показов: {post_price} ⭐\n"
        f"🔒 Цена подписчиков: {subscriber_price} ⭐\n\n"
        f"📉 Минимум показов: {post_min}\n"
        f"📉 Минимум подписчиков: {subscriber_min}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Стоимость раскрытия", callback_data="admin_change_reveal_cost")],
        [InlineKeyboardButton(text="📢 Цена показов", callback_data="adset_ad_post_package_price_stars")],
        [InlineKeyboardButton(text="🔒 Цена подписчиков", callback_data="adset_ad_subscriber_package_price_stars")],
        [InlineKeyboardButton(text="📉 Минимум показов", callback_data="adset_ad_post_min_quantity")],
        [InlineKeyboardButton(text="📉 Минимум подписчиков", callback_data="adset_ad_subscriber_min_quantity")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="admin_back_to_panel")],
    ])
    await safe_delete_message(callback.message)
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data == "admin_open_logs")
async def admin_open_logs_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    await callback.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👁 Все записи", callback_data="admin_logs_view")],
        [InlineKeyboardButton(text="⚠️ Ошибки", callback_data="admin_logs_filter_errors"), InlineKeyboardButton(text="🛡 Админы", callback_data="admin_logs_filter_admins")],
        [InlineKeyboardButton(text="💰 Платежи", callback_data="admin_logs_filter_payments"), InlineKeyboardButton(text="🚨 Жалобы", callback_data="admin_logs_filter_complaints")],
        [InlineKeyboardButton(text="📥 Скачать лог .txt", callback_data="admin_logs_download")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="admin_back_to_panel")],
    ])
    await safe_delete_message(callback.message)
    await callback.message.answer("📋 <b>Логи бота</b>\n\nВыберите действие:", parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data == "admin_open_withdraw")
async def admin_open_withdraw_callback(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    await callback.answer()
    rows = await db.get_pending_withdraw_requests()
    text = f"💸 <b>Заявки на вывод</b>\n\nОжидают обработки: <b>{len(rows)}</b>" if rows else "💸 <b>Заявок на вывод нет.</b>"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="↩️ Назад", callback_data="admin_back_to_panel")
    ]])
    await safe_delete_message(callback.message)
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)

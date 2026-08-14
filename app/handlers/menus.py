from .shared import *

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

@router.message(F.text.in_({"🔧 Админ-панель", "⚙️ Админ-панель CASPER"}))
async def admin_panel_menu(message: Message):
    if message.from_user.id not in ADMIN_IDS: return
    await send_brand_card(
        message,
        "admin",
        "⚙️ <b>Панель управления CASPER</b>\n\nУправление пользователями, рекламой, статистикой и настройками бота.",
        admin_panel(),
    )

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

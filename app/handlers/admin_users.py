from .shared import *


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

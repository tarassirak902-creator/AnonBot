
from .shared import *

# =====================================================================
# 1. КОМАНДЫ
# =====================================================================

@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    was_existing = await db.get_user(user_id) is not None
    ask_token = None
    if command.args and command.args.startswith("ask_"):
        ask_token = command.args[4:].strip() or None

    # Персональная ссылка не должна неожиданно завершать текущий анонимный диалог.
    if ask_token and await db.get_partner(user_id):
        await message.answer(
            "❓ Вы открыли персональную ссылку на анонимный вопрос.\n\n"
            "Сначала завершите текущий диалог, затем откройте ссылку ещё раз.",
            reply_markup=chat_menu(),
        )
        return

    cancel_search_timer(user_id)
    await delete_search_card(message.bot, user_id)
    await db.remove_from_queue(user_id)

    # /start также служит безопасным перезапуском пользовательской сессии.
    partner_id = await db.get_partner(user_id)
    if partner_id:
        await db.add_completed_chat_time(user_id)
        await db.add_completed_chat_time(partner_id)
        await db.end_chat(user_id)
        cancel_inactivity_timer(user_id, partner_id)
        cancel_unread_reminder(user_id)
        cancel_unread_reminder(partner_id)
        try:
            await message.bot.send_message(
                partner_id,
                "👻 <b>CASPER</b>\n\nСобеседник перезапустил бота. Диалог завершён.",
                parse_mode="HTML",
                reply_markup=main_menu(partner_id in ADMIN_IDS),
            )
        except Exception:
            pass

    await db.refresh_user_session(
        user_id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name,
    )
    
    # --- ПРОВЕРКА НА БЛОКИРОВКУ ПРИ СТАРТЕ ---
    user_data = await db.get_user(user_id)
    if await db.is_user_blocked(user_id):
        blocked_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚫 ВЫ ЗАБЛОКИРОВАНЫ", callback_data="is_banned_alert")]
        ])
        await message.answer(
            "⛔ <b>Ваш аккаунт заблокирован администратором!</b>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove()
        )
        await message.answer(
            "Нажмите на кнопку ниже:",
            reply_markup=blocked_kb
        )
        return
    # ----------------------------------------

    referrer_id = None
    if command.args and command.args.startswith("ref_"):
        raw_ref = command.args[4:].strip()
        if raw_ref:
            # Новый формат: постоянный случайный код. Старые числовые ссылки также поддерживаются.
            if raw_ref.isdigit():
                potential_ref = int(raw_ref)
            else:
                potential_ref = await db.get_user_id_by_ref_code(raw_ref)
            if potential_ref and potential_ref != user_id:
                referrer_id = potential_ref

    await db.add_user_with_ref(
        user_id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name,
        None,
    )
    if not was_existing and referrer_id:
        await db.bind_referrer_once(user_id, referrer_id)
    await db.log_action(user_id, "start")
    
    from .advertising import check_mandatory_subscriptions, mandatory_subscriptions_kb
    missing = await check_mandatory_subscriptions(message.bot, user_id)
    if missing:
        await message.answer(
            (
                "🔒 <b>Для использования CASPER необходимо подписаться "
                "на партнёрские сообщества.</b>\n\n"
                "1️⃣ Откройте каждое сообщество кнопкой ниже.\n"
                "2️⃣ Подпишитесь.\n"
                "3️⃣ Вернитесь в бот и нажмите «✅ Проверить подписки».\n\n"
                "После подтверждения подписок главное меню откроется автоматически."
            ),
            parse_mode="HTML",
            reply_markup=mandatory_subscriptions_kb(missing),
        )
        return
    is_admin = user_id in ADMIN_IDS
    if ask_token:
        owner = await db.get_question_owner_by_token(ask_token)
        if owner and int(owner[4] or 0) and int(owner[0]) != user_id:
            await db.record_question_link_visit(int(owner[0]), user_id)
            from .questions import show_question_entry_after_start
            await show_question_entry_after_start(message, ask_token, owner)
            return

    first_name = html.escape(message.from_user.first_name or "друг")
    welcome = (
        f"👻 <b>CASPER приветствует, {first_name}</b>\n\n"
        "<b>Что хотите сделать?</b>\n\n"
        "🚀 Найти случайного собеседника\n"
        "❓ Получать анонимные вопросы\n"
        "🎮 Играть и зарабатывать ⭐\n"
        "👤 Управлять профилем и достижениями\n\n"
        "<i>Главное действие всегда находится на первой кнопке.</i>"
    )
    await send_brand_card(message, "main_menu", welcome, main_menu(is_admin))

@router.message(F.text.in_({"🔗 Пригласить друга", "👥 Пригласить друга", "🎁 Пригласить друга"}))
async def invite_friend(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    _ref_link, share_url, stats = await prepare_referral_data(
        message.bot,
        user_id,
    )
    text = (
        "🎁 <b>Пригласите друга — получите награду</b>\n\n"
        "Друг должен провести <b>5 завершённых диалогов</b>. После этого вы получите "
        "<b>50 виртуальных ⭐</b> на внутренний баланс CASPER GO.\n\n"
        f"👤 Приглашено: <b>{stats['total']}</b>\n"
        f"✅ Активных друзей: <b>{stats['active']}</b>\n"
        f"⭐ Получено наград: <b>{stats['reward_stars']}</b>\n\n"
        "Нажмите кнопку ниже и выберите контакт в Telegram."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📨 Отправить приглашение", url=share_url)],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="referral_stats")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="nav_main_menu")],
    ])
    await send_brand_card(message, "invite", text, kb)

@router.message(F.text.in_({"↩️ Назад", "↩️ Выход"}))
async def back_to_main(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    cancel_search_timer(user_id)
    await delete_search_card(message.bot, user_id)
    await db.remove_from_queue(user_id)
    
    await db.add_completed_chat_time(user_id)
    partner_id = await db.end_chat(user_id)
    if partner_id:
        await db.add_completed_chat_time(partner_id)
        cancel_inactivity_timer(user_id, partner_id)
        cancel_unread_reminder(user_id)
        cancel_unread_reminder(partner_id)
        try:
            await message.bot.send_message(partner_id, "Собеседник завершил общение.", reply_markup=main_menu(partner_id in ADMIN_IDS))
            await message.answer("Вы завершили диалог.", reply_markup=main_menu(user_id in ADMIN_IDS))
            from .advertising import send_ads_to_dialog_users
            await send_ads_to_dialog_users(message.bot, user_id, partner_id, f"manual:{min(user_id, partner_id)}:{max(user_id, partner_id)}:{int(datetime.now().timestamp())}")
            await message.bot.send_message(partner_id, "Хотите узнать, с кем вы только что общались?", reply_markup=reveal_offer_kb(user_id))
            await message.answer("Хотите узнать, с кем вы только что общались?", reply_markup=reveal_offer_kb(partner_id))
        except Exception:
            pass
    else:
        is_admin = user_id in ADMIN_IDS
        await send_brand_card(
            message,
            "main_menu",
            "👻 <b>CASPER</b>\n\nВыберите следующее действие.",
            main_menu(is_admin),
        )



@router.message(Command("paysupport"))
async def payment_support(message: Message):
    await message.answer(
        "💳 <b>Поддержка по платежам</b>\n\n"
        "Пришлите администратору номер рекламной заявки, дату оплаты и описание проблемы. "
        "Не отправляйте никому коды подтверждения или пароль Telegram.",
        parse_mode="HTML",
    )

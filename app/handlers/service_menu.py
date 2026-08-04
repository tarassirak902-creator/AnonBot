from .shared import *

SUPPORT_USERNAME = "dasha_pri"
NEWS_CHANNEL_USERNAME = "caspergoapp"
CURRENT_VERSION = "2.3.9"

ABOUT_TEXT = (
    "👻 <b>CASPER GO</b>\n\n"
    f"<b>Версия:</b> {CURRENT_VERSION}\n\n"
    "CASPER GO — это анонимный Telegram-бот для безопасного общения, знакомств и развлечений.\n\n"
    "<b>Возможности:</b>\n\n"
    "💬 Анонимные диалоги\n🎮 Мини-игры и дуэли\n🎁 Подарки собеседнику\n"
    "💎 VIP-возможности\n💰 Внутренний баланс\n🏆 Игровая статистика\n"
    "🛡️ Система жалоб и модерации\n\n"
    "Мы постоянно развиваем CASPER GO, добавляя новые функции, исправляя ошибки и улучшая удобство использования.\n\n"
    "Спасибо, что выбираете CASPER GO! 💜"
)

PRIVACY_TEXT = (
    "🔐 <b>Политика конфиденциальности</b>\n\n"
    "Используя CASPER GO, вы соглашаетесь с правилами сервиса.\n\n"
    "Мы уделяем особое внимание безопасности пользователей.\n\n"
    "Мы не публикуем ваши персональные данные и не передаём их третьим лицам.\n\n"
    "Для корректной работы бота сохраняются только необходимые данные:\n\n"
    "• Telegram ID\n• настройки профиля\n• баланс аккаунта\n• игровая статистика\n• VIP-статус\n\n"
    "Содержимое анонимных диалогов предназначено только для их участников.\n\n"
    "Все платежи выполняются через официальные сервисы Telegram.\n\n"
    "Если у вас возникли вопросы, вы можете обратиться в службу поддержки."
)


def dismiss_kb(*rows: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    keyboard = list(rows)
    keyboard.append([InlineKeyboardButton(text="✅ Понял, можно удалить", callback_data="service_message_delete")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@router.message(Command("support"))
async def cmd_support(message: Message):
    await message.answer(
        "🛟 <b>Техническая поддержка CASPER</b>\n\nОпишите проблему и приложите скриншот, если он поможет разобраться.",
        parse_mode="HTML",
        reply_markup=dismiss_kb([InlineKeyboardButton(text="🛟 Написать в поддержку", url=f"https://t.me/{SUPPORT_USERNAME}")]),
    )


@router.message(Command("news"))
async def cmd_news(message: Message):
    await message.answer(
        "📢 <b>Новости и обновления CASPER</b>\n\nВсе важные объявления и новые версии публикуются в официальном канале.",
        parse_mode="HTML",
        reply_markup=dismiss_kb([InlineKeyboardButton(text="📢 Перейти в канал", url=f"https://t.me/{NEWS_CHANNEL_USERNAME}")]),
    )


@router.message(Command("about"))
async def cmd_about(message: Message):
    await message.answer(
        ABOUT_TEXT,
        parse_mode="HTML",
        reply_markup=dismiss_kb(
            [InlineKeyboardButton(text="📢 Новости", url=f"https://t.me/{NEWS_CHANNEL_USERNAME}")],
            [InlineKeyboardButton(text="🛟 Поддержка", url=f"https://t.me/{SUPPORT_USERNAME}")],
        ),
    )


@router.message(Command("privacy"))
async def cmd_privacy(message: Message):
    await message.answer(
        PRIVACY_TEXT,
        parse_mode="HTML",
        reply_markup=dismiss_kb([InlineKeyboardButton(text="🛟 Поддержка", url=f"https://t.me/{SUPPORT_USERNAME}")]),
    )


@router.callback_query(F.data == "service_refresh_bot")
async def service_refresh_bot(callback: CallbackQuery, state: FSMContext):
    """Совместимость со старой кнопкой обновления из версии 2.3.8."""
    await callback.answer("CASPER перезапущен")
    user_id = callback.from_user.id
    await state.clear()
    cancel_search_timer(user_id)
    cancel_unread_reminder(user_id)
    await delete_search_card(callback.bot, user_id)
    await db.remove_from_queue(user_id)
    partner_id = await db.get_partner(user_id)
    if partner_id:
        await db.add_completed_chat_time(user_id)
        await db.add_completed_chat_time(partner_id)
        await db.end_chat(user_id)
        cancel_inactivity_timer(user_id, partner_id)
        cancel_unread_reminder(partner_id)
        try:
            await callback.bot.send_message(
                partner_id,
                "👻 <b>CASPER</b>\n\nСобеседник перезапустил бота. Диалог завершён.",
                parse_mode="HTML",
                reply_markup=main_menu(partner_id in ADMIN_IDS),
            )
        except Exception:
            pass
    await db.refresh_user_session(user_id, callback.from_user.username, callback.from_user.first_name, callback.from_user.last_name)
    await db.log_action(user_id, "force_refresh", f"partner={partner_id or 0}")
    await safe_delete_message(callback.message)
    await show_main_menu_screen(callback.message, user_id)


@router.callback_query(F.data == "service_message_delete")
async def service_message_delete(callback: CallbackQuery):
    await callback.answer()
    await safe_delete_message(callback.message)


# Совместимость со старыми сообщениями 2.3.8.
@router.callback_query(F.data.in_({"service_menu_close", "service_menu_back"}))
async def old_service_message_close(callback: CallbackQuery):
    await callback.answer()
    await safe_delete_message(callback.message)


@router.callback_query(F.data == "service_about")
async def old_service_about(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(ABOUT_TEXT, parse_mode="HTML", reply_markup=dismiss_kb())
    await safe_delete_message(callback.message)


@router.callback_query(F.data == "service_privacy")
async def old_service_privacy(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(PRIVACY_TEXT, parse_mode="HTML", reply_markup=dismiss_kb())
    await safe_delete_message(callback.message)

from .shared import *
from app.core.ui_copy import screen, section
from app.core.ui_labels import ButtonText

SUPPORT_USERNAME = "dasha_pri"
NEWS_CHANNEL_USERNAME = "caspergoapp"
CURRENT_VERSION = "2.3.9"

ABOUT_TEXT = screen(
    "👻 О CASPER GO",
    intro=f"Версия {CURRENT_VERSION}",
    sections=(
        section("Возможности", (
            "💬 Анонимные диалоги",
            "🎮 Мини-игры и дуэли",
            "🎁 Подарки собеседнику",
            "👑 VIP-возможности",
            "⭐ Внутренний баланс",
            "🛡 Жалобы и модерация",
        )),
    ),
    footer="Спасибо, что пользуетесь CASPER GO.",
)

PRIVACY_TEXT = screen(
    "🔐 Конфиденциальность",
    intro="Мы сохраняем только данные, необходимые для работы бота.",
    sections=(
        section("Что хранится", (
            "• Telegram ID",
            "• настройки профиля",
            "• баланс и VIP-статус",
            "• игровая статистика",
        )),
        section("Важно", (
            "• персональные данные не публикуются",
            "• платежи проходят через Telegram",
            "• содержимое диалогов предназначено их участникам",
        )),
    ),
    footer="По вопросам обратитесь в поддержку.",
)


def dismiss_kb(*rows: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    keyboard = list(rows)
    keyboard.append([
        InlineKeyboardButton(
            text=ButtonText.CLOSE,
            callback_data="service_message_delete",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@router.message(Command("support"))
async def cmd_support(message: Message):
    await message.answer(
        screen(
            "🛟 Поддержка",
            intro="Опишите проблему и при необходимости приложите скриншот.",
        ),
        parse_mode="HTML",
        reply_markup=dismiss_kb([
            InlineKeyboardButton(
                text="🛟 Написать",
                url=f"https://t.me/{SUPPORT_USERNAME}",
            )
        ]),
    )


@router.message(Command("news"))
async def cmd_news(message: Message):
    await message.answer(
        screen(
            "📢 Новости",
            intro="Обновления и важные объявления публикуются в официальном канале.",
        ),
        parse_mode="HTML",
        reply_markup=dismiss_kb([
            InlineKeyboardButton(
                text="📢 Открыть канал",
                url=f"https://t.me/{NEWS_CHANNEL_USERNAME}",
            )
        ]),
    )


@router.message(Command("about"))
async def cmd_about(message: Message):
    await message.answer(
        ABOUT_TEXT,
        parse_mode="HTML",
        reply_markup=dismiss_kb(
            [InlineKeyboardButton(text=ButtonText.NEWS, url=f"https://t.me/{NEWS_CHANNEL_USERNAME}")],
            [InlineKeyboardButton(text=ButtonText.SUPPORT, url=f"https://t.me/{SUPPORT_USERNAME}")],
        ),
    )


@router.message(Command("privacy"))
async def cmd_privacy(message: Message):
    await message.answer(
        PRIVACY_TEXT,
        parse_mode="HTML",
        reply_markup=dismiss_kb([
            InlineKeyboardButton(text=ButtonText.SUPPORT, url=f"https://t.me/{SUPPORT_USERNAME}")
        ]),
    )


@router.callback_query(F.data == "service_refresh_bot")
async def service_refresh_bot(callback: CallbackQuery, state: FSMContext):
    """Совместимость со старой кнопкой обновления из версии 2.3.8."""
    await callback.answer("Сессия обновлена")
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
                screen(
                    "💬 Диалог завершён",
                    intro="Собеседник обновил сессию бота.",
                ),
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

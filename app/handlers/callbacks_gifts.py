from .shared import *
from .menus import show_gifts


@router.callback_query(F.data.startswith("offer_reveal_"))
async def process_offer_reveal(callback: types.CallbackQuery):
    partner_id = int(callback.data.split("_")[2])
    cost = int(await db.get_setting("reveal_cost"))
    pay_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Узнать за {cost} ⭐ ", pay=True)],
        [InlineKeyboardButton(
            text="↩️ Назад в главное меню",
            callback_data="nav_main_menu",
        )],
    ])
    await callback.message.answer_invoice(
        title="Узнать собеседника",
        description="Раскрыть имя, username и Telegram ID вашего последнего собеседника.",
        payload=f"reveal_{partner_id}",
        provider_token="", currency="XTR", prices=[LabeledPrice(label="Раскрытие личности", amount=cost)],
        start_parameter="reveal", reply_markup=pay_kb
    )
    await callback.answer()

@router.callback_query(F.data == "back_to_gifts_list")
async def back_to_gifts(callback: types.CallbackQuery):
    await callback.answer()
    await safe_delete_message(callback.message)
    await show_gifts(
        callback.message,
        skip_dialog_check=True,
    )


@router.callback_query(F.data.startswith("buy_gift_"))
async def buy_gift(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    partner_info = await db.get_partner(user_id)
    if not partner_info:
        await callback.answer("Вы не в диалоге.", show_alert=True)
        return
    partner_id = partner_info
    gift_id = int(callback.data.split("_")[2])
    gift = await db.get_gift(gift_id)
    if not gift:
        await callback.answer("Подарок не найден.", show_alert=True)
        return
    name, emoji, price = gift

    is_vip = await db.is_user_vip(user_id)
    actual_price = int(price * 0.7) if is_vip else price

    await safe_delete_message(callback.message)
    pay_and_back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Оплатить {actual_price} ⭐", pay=True)],
        [InlineKeyboardButton(text="↩️ Назад к подаркам", callback_data="back_to_gifts_list")]
    ])

    await callback.message.answer_invoice(
        title=f"{emoji} {name}", description=f"Отправка подарка {emoji} {name} для вашего собеседника.",
        payload=f"gift_{gift_id}_{partner_id}", provider_token="", currency="XTR",
        prices=[LabeledPrice(label=f"Подарок: {name}", amount=actual_price)],
        start_parameter="gift", reply_markup=pay_and_back_kb
    )
    await callback.answer()

@router.callback_query(F.data.startswith("complaint_"))
async def handle_complaint(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    partner_info = await db.get_partner(user_id)
    if not partner_info:
        await callback.answer("Вы не в диалоге.", show_alert=True)
        return
        
    partner_id = partner_info
    reason_map = {
        "complaint_18": "🔞 Контент 18+", "complaint_beg": "💰 Попрошайничество",
        "complaint_scam": "🎣 Скам", "complaint_spam": "🚫 Спам",
        "complaint_insult": "🤬 Оскорбления", "complaint_other": "📌 Другое", "complaint_cancel": None
    }
    
    reason = reason_map.get(callback.data)
    if reason is None:
        await callback.answer("Отменено.")
        await safe_delete_message(callback.message)
        await callback.message.answer(
            "💬 <b>Вы вернулись в диалог.</b>",
            parse_mode="HTML",
            reply_markup=chat_menu(),
        )
        return

    await db.add_complaint(user_id, partner_id, reason)
    await db.update_user_stats(user_id, complaints=1)
    await db.log_action(user_id, "complaint_sent", f"на {partner_id}: {reason}")

    try:
        sender = await callback.bot.get_chat(user_id)
        offender = await callback.bot.get_chat(partner_id)
        s_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
        s_un = f"@{sender.username}" if sender.username else "нет"
        o_name = f"{offender.first_name or ''} {offender.last_name or ''}".strip()
        o_un = f"@{offender.username}" if offender.username else "нет"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        admin_text = (
            f"🚨 <b>НОВАЯ ЖАЛОБА ОТ ПОЛЬЗОВАТЕЛЯ!</b>\n\n"
            f"⚠️ <b>Причина:</b> {html.escape(reason)}\n🕐 <b>Время:</b> {now}\n\n"
            f"👤 <b>Нарушитель:</b>\n├ Имя: {html.escape(o_name)}\n├ Username: {html.escape(o_un)}\n└ ID: <code>{partner_id}</code>\n\n"
            f"📩 <b>Отправитель жалобы:</b>\n├ Имя: {html.escape(s_name)}\n├ Username: {html.escape(s_un)}\n└ ID: <code>{user_id}</code>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚠️ Выдать варн", callback_data=f"log_warn_{partner_id}"), InlineKeyboardButton(text="🔇 Ограничить (24ч)", callback_data=f"log_mute_{partner_id}")],
            [InlineKeyboardButton(text="⛔ Бан навсегда", callback_data=f"log_ban_{partner_id}")]
        ])
        await callback.bot.send_message(LOG_CHANNEL_ID, admin_text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        logger.exception(
            "Ошибка отправки жалобы: user_id=%s, partner_id=%s",
            user_id,
            partner_id,
        )

    await callback.answer("✅ Жалоба отправлена администраторам.", show_alert=True)
    await callback.message.delete()


@router.callback_query(F.data == "reveal_back_to_chat")
async def reveal_back_to_chat_handler(callback: CallbackQuery):
    await callback.answer()
    await safe_delete_message(callback.message)

    if await db.get_partner(callback.from_user.id):
        await callback.message.answer(
            "💬 <b>Вы вернулись в диалог.</b>",
            parse_mode="HTML",
            reply_markup=chat_menu(),
        )
        return

    await show_main_menu_screen(
        callback.message,
        callback.from_user.id,
    )

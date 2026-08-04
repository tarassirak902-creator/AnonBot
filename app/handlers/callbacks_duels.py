from .shared import *
from .profile_view import send_profile_screen

@router.callback_query(F.data.startswith("pay_duel_accept_"))
async def accept_duel_pay_invoice_handler(callback: CallbackQuery):
    duel_id = int(callback.data.split("_")[3])
    duel = await db.get_game_duel(duel_id)
    if not duel or duel[4] != 'waiting':
        await callback.answer("Дуэль недействительна.", show_alert=True)
        return

    bet = duel[3]
    pay_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⭐ Оплатить {bet} ⭐ для дуэли", pay=True)]
    ])

    await callback.message.answer_invoice(
        title="Принятие дуэли",
        description=f"Принятие дуэли со ставкой {bet} ⭐.",
        payload=f"duel_accept_{duel_id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"Дуэль ({bet} ⭐)", amount=bet)],
        start_parameter="duel_accept",
        reply_markup=pay_kb
    )
    await callback.answer()

@router.callback_query(F.data.startswith("decline_duel_"))
async def decline_duel_handler(callback: CallbackQuery):
    duel_id = int(callback.data.split("_")[2])
    duel = await db.get_game_duel(duel_id)
    if duel:
        creator_id = duel[1]
        await db.update_game_duel_status(duel_id, 'declined')
        try:
            await callback.bot.send_message(
                creator_id,
                "❌ Собеседник отклонил вызов на дуэль.",
            )
        except Exception as exc:
            await db.log_action(
                callback.from_user.id,
                "duel_decline_notify_error",
                f"creator_id={creator_id}; error={exc}",
            )

    await callback.answer("Дуэль отклонена.")
    await callback.message.delete()

import html


def _admin_label(user) -> str:
    name = " ".join(x for x in (user.first_name, user.last_name) if x).strip()
    return f"{name} (@{user.username})" if name and user.username else (name or (f"@{user.username}" if user.username else "Администратор"))


async def _render_processed_withdraw(callback: CallbackQuery, req, status: str) -> None:
    admin = callback.from_user
    action = "Одобрена" if status == "approved" else "Отклонена"
    base = callback.message.html_text or callback.message.text or ""
    marker = "✅ <b>Заявка обработана</b>"
    if marker not in base:
        footer = (
            "\n\n━━━━━━━━━━━━━━\n"
            f"{marker}\n"
            f"👤 Администратор: <b>{html.escape(_admin_label(admin))}</b>\n"
            f"🆔 ID администратора: <code>{admin.id}</code>\n"
            f"⚙️ Действие: <b>{action}</b>"
        )
        try:
            await callback.message.edit_text(base + footer, parse_mode="HTML", reply_markup=None)
        except Exception:
            await callback.message.edit_reply_markup(reply_markup=None)

    log_chat_id = req[7] if len(req) > 7 else None
    log_message_id = req[8] if len(req) > 8 else None
    if log_chat_id and log_message_id and (callback.message.chat.id != log_chat_id or callback.message.message_id != log_message_id):
        try:
            original = await callback.bot.edit_message_reply_markup(chat_id=log_chat_id, message_id=log_message_id, reply_markup=None)
            # Telegram Bot API не возвращает старый текст при edit_reply_markup; используем карточку заявки.
            user = await db.get_user(req[1])
            username = f"@{user[1]}" if user and user[1] else "нет"
            full_name = " ".join(x for x in ((user[2] if user else None), (user[3] if user else None)) if x).strip() or "не указано"
            text = (
                "💸 <b>ЗАЯВКА НА ВЫВОД ЗВЁЗД</b>\n\n"
                f"🆔 <b>ID Заявки:</b> #{req[0]}\n"
                f"👤 <b>Пользователь:</b> {html.escape(full_name)} ({html.escape(username)})\n"
                f"🆔 <b>ID:</b> <code>{req[1]}</code>\n"
                f"⭐ <b>Сумма вывода:</b> {req[2]} ⭐\n\n"
                "━━━━━━━━━━━━━━\n"
                f"{marker}\n"
                f"👤 Администратор: <b>{html.escape(_admin_label(admin))}</b>\n"
                f"🆔 ID администратора: <code>{admin.id}</code>\n"
                f"⚙️ Действие: <b>{action}</b>"
            )
            await callback.bot.edit_message_text(chat_id=log_chat_id, message_id=log_message_id, text=text, parse_mode="HTML", reply_markup=None)
        except Exception:
            logger.exception(
                "Не удалось обновить служебное сообщение вывода: "
                "request_id=%s, chat_id=%s, message_id=%s",
                req[0],
                log_chat_id,
                log_message_id,
            )


async def _process_withdraw(callback: CallbackQuery, status: str) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        return
    req_id = int(callback.data.rsplit("_", 1)[1])
    req = await db.process_withdraw_request(req_id, status, callback.from_user.id)
    if not req:
        await callback.answer("Заявка уже обработана другим администратором.", show_alert=True)
        return
    user_id, amount = req[1], req[2]
    try:
        if status == "approved":
            text = f"✅ <b>Ваша заявка #{req_id} на вывод {amount} ⭐ одобрена.</b>\n\nЗвёзды будут переведены вам в ближайшее время."
        else:
            text = f"❌ <b>Ваша заявка #{req_id} на вывод {amount} ⭐ отклонена.</b>\n\nСредства возвращены на баланс бота."
        await callback.bot.send_message(user_id, text, parse_mode="HTML")
    except Exception:
        logger.exception(
            "Не удалось уведомить пользователя о выводе: "
            "request_id=%s, user_id=%s, status=%s",
            req_id,
            user_id,
            status,
        )

    await _render_processed_withdraw(callback, req, status)
    await callback.answer("Заявка обработана.", show_alert=True)


@router.callback_query(F.data.startswith("withdraw_approve_"))
async def admin_approve_withdraw(callback: CallbackQuery):
    await _process_withdraw(callback, "approved")


@router.callback_query(F.data.startswith("withdraw_reject_"))
async def admin_reject_withdraw(callback: CallbackQuery):
    await _process_withdraw(callback, "rejected")

@router.callback_query(F.data == "admin_change_reveal_cost")
async def start_change_reveal_cost(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await callback.answer()
    text = "⭐ <b>Введите новую стоимость раскрытия собеседника (в Звёздах):</b>"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ Назад в настройки", callback_data="admin_back_to_settings")]
    ])
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await state.set_state(AdminSettings.waiting_for_reveal_cost)

@router.callback_query(F.data == "admin_back_to_settings")
async def admin_back_to_settings_handler(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS: return
    await state.clear()
    await callback.answer()
    cost = await db.get_setting("reveal_cost") or "15"
    post_price = await db.get_setting("ad_post_package_price_stars") or "150"
    subscriber_price = await db.get_setting("ad_subscriber_package_price_stars") or "100"
    post_min = await db.get_setting("ad_post_min_quantity") or "100"
    subscriber_min = await db.get_setting("ad_subscriber_min_quantity") or "50"
    text = (f"⚙️ <b>Настройки стоимости и рекламы</b>\n\n"
            f"👤 Стоимость раскрытия: {cost} ⭐\n📢 Цена показов: {post_price} ⭐\n"
            f"🔒 Цена подписчиков: {subscriber_price} ⭐\n\n📉 Минимум показов: {post_min}\n"
            f"📉 Минимум подписчиков: {subscriber_min}")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Стоимость раскрытия", callback_data="admin_change_reveal_cost")],
        [InlineKeyboardButton(text="📢 Цена показов", callback_data="adset_ad_post_package_price_stars")],
        [InlineKeyboardButton(text="🔒 Цена подписчиков", callback_data="adset_ad_subscriber_package_price_stars")],
        [InlineKeyboardButton(text="📉 Минимум показов", callback_data="adset_ad_post_min_quantity")],
        [InlineKeyboardButton(text="📉 Минимум подписчиков", callback_data="adset_ad_subscriber_min_quantity")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="admin_back_to_panel")],
    ])
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data == "profile_refresh")
async def profile_refresh_handler(callback: types.CallbackQuery):
    if not await db.get_user(callback.from_user.id):
        await callback.answer("Ошибка загрузки профиля.", show_alert=True)
        return
    await callback.answer("Данные обновлены!")
    try:
        await callback.message.delete()
    except Exception:
        pass
    await send_profile_screen(callback.message, callback.from_user.id)

@router.callback_query(F.data == "profile_my_received_gifts")
async def profile_received_gifts_handler(callback: types.CallbackQuery):
    await callback.answer()
    gifts = await db.get_user_received_gifts(callback.from_user.id)
    if not gifts:
        text = "🎀 <b>ПОЛУЧЕННЫЕ ПОДАРКИ</b>\n───────────────\n\n<i>У вас пока нет полученных подарков 🎁</i>"
    else:
        text = "🎀 <b>ПОЛУЧЕННЫЕ ПОДАРКИ</b>\n───────────────\n\n"
        for emoji, name, price, ts in gifts:
            text += f"• {emoji or '🎁'} <b>{name or 'Подарок'}</b> ({price} ⭐) — <i>{ts[:10]}</i>\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ Назад в профиль", callback_data="profile_back")]
    ])
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data == "profile_my_sent_gifts")
async def profile_sent_gifts_handler(callback: types.CallbackQuery):
    await callback.answer()
    gifts = await db.get_user_sent_gifts(callback.from_user.id)
    if not gifts:
        text = "🎁 <b>ОТПРАВЛЕННЫЕ ПОДАРКИ</b>\n───────────────\n\n<i>Вы ещё не отправляли подарки 🎁</i>"
    else:
        text = "🎁 <b>ОТПРАВЛЕННЫЕ ПОДАРКИ</b>\n───────────────\n\n"
        for emoji, name, price, ts in gifts:
            text += f"• {emoji or '🎁'} <b>{name or 'Подарок'}</b> ({price} ⭐) — <i>{ts[:10]}</i>\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ Назад в профиль", callback_data="profile_back")]
    ])
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data == "profile_my_revealed")
async def profile_revealed_handler(callback: types.CallbackQuery):
    await callback.answer()
    revealed = await db.get_revealed_partners(callback.from_user.id)
    if not revealed:
        text = "🔍 <b>РАСКРЫТЫЕ СОБЕСЕДНИКИ</b>\n───────────────\n\n<i>Вы ещё не раскрывали собеседников 🔒</i>"
    else:
        text = "🔍 <b>РАСКРЫТЫЕ СОБЕСЕДНИКИ</b>\n───────────────\n\n"
        for partner_id, timestamp in revealed[:10]:
            try:
                partner = await callback.bot.get_chat(partner_id)
                name = f"{partner.first_name or ''} {partner.last_name or ''}".strip()
                username = f"@{partner.username}" if partner.username else f"ID {partner_id}"
                text += f"• <b>{name}</b> ({username}) — <i>{timestamp[:10]}</i>\n"
            except Exception:
                text += f"• <code>ID {partner_id}</code> — <i>{timestamp[:10]}</i>\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ Назад в профиль", callback_data="profile_back")]
    ])
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data == "close_gifts_menu")
async def close_gifts_menu_handler(callback: types.CallbackQuery):
    await callback.answer()
    await safe_delete_message(callback.message)
    await callback.message.answer(
        "💬 <b>Вы вернулись в диалог.</b>",
        parse_mode="HTML",
        reply_markup=chat_menu(),
    )

@router.callback_query(F.data == "reminder_find_partner")
async def process_reminder_search(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("Выберите действие:", reply_markup=main_menu(callback.from_user.id in ADMIN_IDS))

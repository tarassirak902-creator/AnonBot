from __future__ import annotations

import html

from aiogram import F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, Message, CallbackQuery

from .shared import router, ADMIN_IDS, send_brand_card, hide_reply_keyboard
from app import database as db
from app.core.keyboards import main_menu


class AdOrder(StatesGroup):
    waiting_post = State()
    waiting_post_quantity = State()
    waiting_channel = State()
    waiting_subscriber_quantity = State()
    confirming_order = State()
    editing_quantity = State()


class AdAdminEdit(StatesGroup):
    waiting_value = State()


class AdRejectReason(StatesGroup):
    waiting_reason = State()


class AdExtendOrder(StatesGroup):
    waiting_quantity = State()


async def _delete_current(message):
    try:
        await message.delete()
    except Exception:
        pass


def _back_kb(callback_data: str):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data=callback_data)]])


def _confirm_order_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить на модерацию", callback_data="ads_submit_order")],
        [InlineKeyboardButton(text="✏️ Изменить", callback_data="ads_change_draft")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="ads_cancel_draft")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="ads_draft_back")],
    ])


async def _show_advertising_menu(message, state):
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Рекламный пост", callback_data="ads_buy_post")],
        [InlineKeyboardButton(text="🔒 Обязательная подписка", callback_data="ads_buy_subscription")],
        [InlineKeyboardButton(text="📋 Мои заказы", callback_data="ads_my_orders")],
        [InlineKeyboardButton(text="📊 Моя статистика", callback_data="ads_my_statistics")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="ads_close_menu")],
    ])
    await send_brand_card(
        message,
        "advertising",
        "📢 <b>Реклама в CASPER</b>\n\nПродвигайте свои проекты среди пользователей CASPER.\nВыберите нужный раздел:",
        kb,
    )


async def send_post_dialog_ad(bot, user_id: int, dialog_key: str, exclude_campaign_id: int | None = None):
    campaign = await db.reserve_next_ad_campaign(user_id, dialog_key, exclude_campaign_id)
    if not campaign and exclude_campaign_id is not None:
        campaign = await db.reserve_next_ad_campaign(user_id, dialog_key, None)
    if not campaign:
        return None
    campaign_id, source_chat_id, source_message_id = campaign
    try:
        await bot.copy_message(user_id, source_chat_id, source_message_id)
    except Exception as exc:
        await db.release_ad_reservation(campaign_id, user_id, dialog_key)
        await db.log_action(user_id, "ad_delivery_error", f"campaign={campaign_id}: {exc}")
        return None
    completed, advertiser_id = await db.confirm_ad_impression(campaign_id, user_id, dialog_key)
    if completed:
        try:
            await bot.send_message(advertiser_id, f"✅ Рекламная кампания №{campaign_id} завершена. Все оплаченные показы выполнены.")
        except Exception:
            pass
    return campaign_id


async def send_ads_to_dialog_users(bot, user1_id: int, user2_id: int, dialog_key: str):
    first = await send_post_dialog_ad(bot, user1_id, dialog_key)
    await send_post_dialog_ad(bot, user2_id, dialog_key, exclude_campaign_id=first)


@router.message(F.text.in_({"📣 Купить рекламу", "📢 Купить рекламу", "📢 Реклама в CASPER"}))
async def advertising_menu(message: Message, state: FSMContext):
    await hide_reply_keyboard(message)
    await _show_advertising_menu(message, state)


@router.callback_query(F.data == "ads_close_menu")
async def ads_close_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await _delete_current(callback.message)
    await show_main_menu_screen(callback.message, callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data == "ads_buy_post")
async def ads_buy_post(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdOrder.waiting_post)
    await _delete_current(callback.message)
    await callback.message.answer("Перешлите или отправьте рекламный пост, который хотите что бы публиковался в Casper.", reply_markup=_back_kb("ads_back_menu"))
    await callback.answer()


@router.message(AdOrder.waiting_post)
async def ads_receive_post(message: Message, state: FSMContext):
    preview_text = html.escape(message.text or message.caption or "")
    if not preview_text:
        if message.photo:
            preview_text = "📷 Фотография"
        elif message.video:
            preview_text = "🎬 Видео"
        elif message.animation:
            preview_text = "🎞 GIF-анимация"
        elif message.document:
            preview_text = "📎 Документ"
        elif message.audio:
            preview_text = "🎵 Аудио"
        elif message.voice:
            preview_text = "🎤 Голосовое сообщение"
        else:
            preview_text = "Рекламный пост без текстового описания"
    await state.update_data(
        source_chat_id=message.chat.id,
        source_message_id=message.message_id,
        source_preview_text=preview_text[:3000],
    )
    minimum = int(await db.get_setting("ad_post_min_quantity") or 100)
    price = int(await db.get_setting("ad_post_package_price_stars") or 150)
    await state.set_state(AdOrder.waiting_post_quantity)
    await message.answer(f"Введите количество просмотров. Минимум {minimum}.", reply_markup=_back_kb("ads_back_post"))


@router.message(AdOrder.waiting_post_quantity)
async def ads_post_quantity(message: Message, state: FSMContext):
    minimum = int(await db.get_setting("ad_post_min_quantity") or 100)
    price = int(await db.get_setting("ad_post_package_price_stars") or 150)
    text = (message.text or "").strip()
    if not text.isdigit() or int(text) < minimum or int(text) % minimum:
        await message.answer(f"Количество должно быть не меньше {minimum} и кратно {minimum}.")
        return
    quantity = int(text)
    data = await state.get_data()
    total = quantity // minimum * price
    await state.update_data(campaign_type="post", quantity=quantity, package_size=minimum, package_price=price, total=total)
    await state.set_state(AdOrder.confirming_order)
    await message.answer(
        f"📢 <b>Ваш заказ</b>\n\nКоличество показов: {quantity}\n\nСтоимость: {total} ⭐\n\n"
        "После одобрения администрацией вам будет выставлен счёт на оплату Telegram Stars.",
        parse_mode="HTML", reply_markup=_confirm_order_kb())


@router.callback_query(F.data == "ads_buy_subscription")
async def ads_buy_subscription(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Канал", callback_data="ads_community_channel")],
        [InlineKeyboardButton(text="👥 Группа", callback_data="ads_community_group")],
    ])
    kb.inline_keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="ads_back_menu")])
    await _delete_current(callback.message)
    await callback.message.answer("Выберите тип сообщества для обязательной подписки:", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.in_({"ads_community_channel", "ads_community_group"}))
async def ads_choose_community_type(callback: CallbackQuery, state: FSMContext):
    community_type = "channel" if callback.data.endswith("channel") else "group"
    await state.update_data(community_type=community_type)
    await state.set_state(AdOrder.waiting_channel)
    await _delete_current(callback.message)
    await callback.message.answer(
        "Для запуска рекламы выполни действия:\n"
        "1. Добавьте нашего бота @anonchatvoice_bot к себе администратором;\n"
        "2. Отправьте @username или ссылку на ваш канал или группу.",
        reply_markup=_back_kb("ads_back_community_type")
    )
    await callback.answer()


@router.message(AdOrder.waiting_channel)
async def ads_receive_channel(message: Message, state: FSMContext):
    raw_ref = (message.text or "").strip()
    if not raw_ref:
        await message.answer("Отправьте @username или публичную ссылку сообщества.")
        return
    await state.update_data(community_raw_ref=raw_ref)
    await _check_advertising_community(message, state, raw_ref)


def _community_check_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Проверить", callback_data="ads_check_community")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="ads_back_community_type")],
    ])


async def _check_advertising_community(message: Message, state: FSMContext, raw_ref: str):
    data = await state.get_data()
    requested_type = data.get("community_type", "channel")
    lookup_ref = raw_ref
    if raw_ref.startswith("https://t.me/") and "+" not in raw_ref:
        lookup_ref = "@" + raw_ref.rstrip("/").rsplit("/", 1)[-1]
    elif raw_ref.lstrip("-").isdigit():
        lookup_ref = int(raw_ref)
    try:
        chat = await message.bot.get_chat(lookup_ref)
        actual_type = getattr(chat.type, "value", str(chat.type))
        is_channel = actual_type == "channel"
        is_group = actual_type in {"group", "supergroup"}
        if requested_type == "channel" and not is_channel:
            await message.answer("Это не канал. Отправьте данные канала или вернитесь и выберите группу.")
            return
        if requested_type == "group" and not is_group:
            await message.answer("Это не группа. Отправьте данные группы или вернитесь и выберите канал.")
            return
        me = await message.bot.get_me()
        bot_member = await message.bot.get_chat_member(chat.id, me.id)
        if bot_member.status not in {"administrator", "creator"}:
            await message.answer(
                "Сначала добавьте бота администратором в это сообщество.",
                reply_markup=_community_check_kb(),
            )
            return
    except Exception:
        await message.answer(
            "Не удалось проверить сообщество. Убедитесь, что бот добавлен администратором, "
            "а затем нажмите «Проверить».",
            reply_markup=_community_check_kb(),
        )
        return
    username = getattr(chat, "username", None)
    public_url = f"https://t.me/{username}" if username else None
    display_ref = raw_ref if raw_ref.startswith(("@", "http://", "https://")) else public_url
    await state.update_data(
        channel=str(chat.id), community_type=requested_type,
        community_title=getattr(chat, "title", None) or "Без названия",
        community_url=display_ref
    )
    minimum = int(await db.get_setting("ad_subscriber_min_quantity") or 50)
    await state.set_state(AdOrder.waiting_subscriber_quantity)
    await message.answer(
        f"Введите количество подписчиков. Минимум {minimum}.",
        reply_markup=_back_kb("ads_back_community"),
    )


@router.callback_query(F.data == "ads_check_community")
async def ads_check_community(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    raw_ref = data.get("community_raw_ref")
    if not raw_ref:
        await callback.answer("Сначала отправьте ссылку или @username.", show_alert=True)
        return
    await _delete_current(callback.message)
    await _check_advertising_community(callback.message, state, raw_ref)
    await callback.answer()


@router.message(AdOrder.waiting_subscriber_quantity)
async def ads_subscriber_quantity(message: Message, state: FSMContext):
    minimum = int(await db.get_setting("ad_subscriber_min_quantity") or 50)
    price = int(await db.get_setting("ad_subscriber_package_price_stars") or 100)
    text = (message.text or "").strip()
    if not text.isdigit() or int(text) < minimum or int(text) % minimum:
        await message.answer(f"Количество должно быть не меньше {minimum} и кратно {minimum}.")
        return
    quantity = int(text)
    data = await state.get_data()
    total = quantity // minimum * price
    await state.update_data(campaign_type="subscription", quantity=quantity, package_size=minimum, package_price=price, total=total)
    await state.set_state(AdOrder.confirming_order)
    unit = "подписчиков" if data.get("community_type") == "channel" else "участников"
    destination = data.get("community_raw_ref") or data.get("community_url") or "не указано"
    await message.answer(
        f"🔒 <b>Ваш заказ</b>\n\n"
        f"Количество {unit}: {quantity}\n"
        f"Реклама на: {html.escape(str(destination))}\n\n"
        f"Стоимость: {total} ⭐\n\n"
        "После одобрения администрацией вам будет выставлен счёт на оплату Telegram Stars.",
        parse_mode="HTML", reply_markup=_confirm_order_kb())


@router.callback_query(F.data == "ads_submit_order")
async def ads_submit_order(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    ctype = data.get("campaign_type")
    if ctype == "post":
        order_id = await db.create_ad_order(callback.from_user.id, "post", data["quantity"], data["package_size"], data["package_price"], data["total"], source_chat_id=data["source_chat_id"], source_message_id=data["source_message_id"], source_preview_text=data.get("source_preview_text"))
    elif ctype == "subscription":
        order_id = await db.create_ad_order(callback.from_user.id, "subscription", data["quantity"], data["package_size"], data["package_price"], data["total"], channel_ref=data["channel"], community_type=data.get("community_type"), community_title=data.get("community_title"), community_url=data.get("community_url"))
    else:
        await callback.answer("Черновик заявки не найден.", show_alert=True); return
    await state.clear()
    await _delete_current(callback.message)
    await callback.message.answer(f"✅ Заявка №{order_id} отправлена на модерацию.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📋 Мои заказы", callback_data="ads_my_orders")],[InlineKeyboardButton(text="◀️ Назад", callback_data="ads_back_menu")]]))
    await notify_admins_new_order(callback.bot, order_id)
    await callback.answer()

@router.callback_query(F.data == "ads_change_draft")
async def ads_change_draft(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data(); ctype=data.get("campaign_type")
    await _delete_current(callback.message)
    if ctype == "post":
        await state.set_state(AdOrder.waiting_post_quantity)
        await callback.message.answer("Введите новое количество показов:", reply_markup=_back_kb("ads_draft_back"))
    else:
        await state.set_state(AdOrder.waiting_subscriber_quantity)
        await callback.message.answer("Введите новое количество подписчиков или участников:", reply_markup=_back_kb("ads_draft_back"))
    await callback.answer()

@router.callback_query(F.data == "ads_cancel_draft")
async def ads_cancel_draft(callback: CallbackQuery, state: FSMContext):
    await state.clear(); await _delete_current(callback.message); await _show_advertising_menu(callback.message, state); await callback.answer()

@router.callback_query(F.data.in_({"ads_back_menu","ads_draft_back"}))
async def ads_back_menu(callback: CallbackQuery, state: FSMContext):
    await _delete_current(callback.message); await _show_advertising_menu(callback.message, state); await callback.answer()

@router.callback_query(F.data == "ads_back_post")
async def ads_back_post(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdOrder.waiting_post); await _delete_current(callback.message)
    await callback.message.answer("Перешлите или отправьте рекламный пост, который хотите что бы публиковался в Casper.", reply_markup=_back_kb("ads_back_menu")); await callback.answer()

@router.callback_query(F.data == "ads_back_community_type")
async def ads_back_community_type(callback: CallbackQuery, state: FSMContext):
    await _delete_current(callback.message)
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📢 Канал",callback_data="ads_community_channel")],[InlineKeyboardButton(text="👥 Группа",callback_data="ads_community_group")],[InlineKeyboardButton(text="◀️ Назад",callback_data="ads_back_menu")]])
    await callback.message.answer("Выберите тип сообщества:",reply_markup=kb); await callback.answer()

@router.callback_query(F.data == "ads_back_community")
async def ads_back_community(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdOrder.waiting_channel); await _delete_current(callback.message)
    await callback.message.answer("Отправьте ссылку или @username сообщества.",reply_markup=_back_kb("ads_back_community_type")); await callback.answer()


async def notify_admins_new_order(bot, order_id: int):
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, "📣 Новая рекламная заявка")
        except Exception:
            pass


async def _send_ad_order_invoice(bot, advertiser_id: int, order_id: int, total: int):
    pay_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"⭐  Оплатить {total} ⭐ ", pay=True)],
            [InlineKeyboardButton(
                text="◀️ Вернуться к заказу",
                callback_data=f"ads_order_view_{order_id}",
            )],
        ]
    )
    await bot.send_invoice(
        advertiser_id,
        title="Заявка на рекламу одобрена",
        description="Ваша заявка на рекламу одобрена! Оплатите услугу и она автоматически включится.",
        payload=f"ad_order_{order_id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Рекламная кампания", amount=total)],
        reply_markup=pay_kb,
    )


@router.callback_query(F.data.startswith("ads_approve_"))
async def ads_approve(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    order_id = int(callback.data.rsplit("_", 1)[1])
    order = await db.moderate_ad_order(order_id, True, callback.from_user.id)
    if not order:
        await callback.answer("Заявка уже обработана.", show_alert=True)
        return
    advertiser_id, total = order
    try:
        await callback.bot.send_message(
            advertiser_id,
            f"✅ Заявка №{order_id} одобрена.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="👁 Просмотреть", callback_data=f"ads_order_view_{order_id}")
            ]]),
        )
    except Exception:
        pass
    text, kb = await _render_admin_campaign(order_id)
    await callback.message.edit_text(
        f"✅ Заявка №{order_id} одобрена. Пользователю отправлено уведомление.\n\n{text}",
        parse_mode="HTML", reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ads_reject_"))
async def ads_reject(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    order_id = int(callback.data.rsplit("_", 1)[1])
    await state.update_data(reject_order_id=order_id, reject_message_id=callback.message.message_id)
    await state.set_state(AdRejectReason.waiting_reason)
    await callback.message.answer(f"Введите причину отклонения заявки №{order_id}.")
    await callback.answer()


@router.message(AdRejectReason.waiting_reason)
async def ads_reject_reason(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    reason = (message.text or "").strip()
    if not reason:
        await message.answer("Введите причину текстом.")
        return
    data = await state.get_data()
    order_id = int(data.get("reject_order_id", 0))
    order = await db.moderate_ad_order(order_id, False, message.from_user.id, reason[:1000])
    await state.clear()
    if not order:
        await message.answer("Заявка уже обработана.")
        return
    try:
        await message.bot.send_message(
            order[0],
            f"❌ Рекламная заявка №{order_id} отклонена.\n\n<b>Причина:</b> {html.escape(reason[:1000])}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="👁 Просмотреть", callback_data=f"ads_order_view_{order_id}")
            ]]),
        )
    except Exception:
        pass
    await message.answer(f"❌ Заявка №{order_id} отклонена. Причина отправлена пользователю.")


async def _display_destination(bot, channel_ref, community_url):
    for value in (community_url, channel_ref):
        if value and str(value).startswith(("@", "http://", "https://")):
            return str(value)
    if channel_ref:
        try:
            chat = await bot.get_chat(channel_ref)
            username = getattr(chat, "username", None)
            if username:
                return f"@{username}"
        except Exception:
            pass
    return "Ссылка недоступна"


def _fmt_dt(value):
    return str(value) if value else "—"


@router.callback_query(F.data == "ads_my_statistics")
async def ads_my_statistics(callback: CallbackQuery):
    completed_orders, total_views, total_subscribers = await db.get_user_ad_statistics(callback.from_user.id)
    text = (
        "📊 <b>Моя статистика</b>\n\n"
        f"📋 Завершено заявок: {completed_orders or 0}\n\n"
        f"👁 Всего просмотров: {total_views or 0:,}\n\n"
        f"👥 Всего подписчиков: {total_subscribers or 0:,}"
    ).replace(",", " ")
    await _delete_current(callback.message)
    await callback.message.answer(text, parse_mode="HTML", reply_markup=_back_kb("ads_back_menu"))
    await callback.answer()


@router.callback_query(F.data == "ads_my_orders")
async def ads_my_orders(callback: CallbackQuery):
    rows = await db.get_user_ad_orders(callback.from_user.id)
    buttons = []
    for row in rows:
        order_id, campaign_type, status, completed, target, total, channel_ref, community_url = row
        kind = "📢 Рекламный пост" if campaign_type == "post" else "🔒 Обязательная подписка"
        buttons.append([
            InlineKeyboardButton(
                text=f"Заявка {order_id} ({kind})",
                callback_data=f"ads_order_view_{order_id}",
            )
        ])
    if rows:
        text = (
            "📋 <b>Мои заказы</b>\n\n"
            "Перейди в заявку, чтобы просмотреть этап заявки и статистику."
        )
    else:
        text = "📋 <b>Мои заказы</b>\n\nУ вас пока нет рекламных заявок."
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="ads_back_menu")])
    await _delete_current(callback.message)
    await callback.message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()


@router.callback_query(F.data.startswith("ads_order_pay_"))
async def ads_order_pay(callback: CallbackQuery):
    order_id = int(callback.data.rsplit("_", 1)[1])
    row = await db.get_ad_order_for_user(order_id, callback.from_user.id)
    if not row:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return
    if row[2] != "awaiting_payment":
        await callback.answer("Эта заявка сейчас недоступна для оплаты.", show_alert=True)
        return
    await _send_ad_order_invoice(callback.bot, callback.from_user.id, order_id, row[5])
    await callback.answer("Счёт отправлен.")


@router.callback_query(F.data.startswith("ads_order_view_"))
async def ads_order_view(callback: CallbackQuery):
    oid = int(callback.data.rsplit("_", 1)[1])
    row = await db.get_ad_order_for_user(oid, callback.from_user.id)
    if not row:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return
    (order_id, campaign_type, status, target, completed, total, source_chat_id, source_message_id,
     channel_ref, community_type, community_title, community_url, package_size, package_price,
     created_at, started_at, completed_at, source_preview_text, rejection_reason) = row
    destination = await _display_destination(callback.bot, channel_ref, community_url)
    type_text = "📢 Рекламный пост" if campaign_type == "post" else ("👥 Группа" if community_type == "group" else "📢 Канал")
    title = community_title or ("Рекламный пост" if campaign_type == "post" else "Без названия")
    noun = "показов" if campaign_type == "post" else ("участников" if community_type == "group" else "подписчиков")
    post_preview = ""
    if campaign_type == "post" and not (source_chat_id and source_message_id):
        preview = source_preview_text or "Предпросмотр рекламного поста недоступен для этой старой заявки."
        post_preview = f"\n<b>Рекламный пост:</b>\n<blockquote>{preview}</blockquote>\n"

    if status == "awaiting_payment":
        text = (
            f"✅ <b>Заявка №{order_id} одобрена.</b>\n"
            "Оплатите услугу и она автоматически включится.\n\n"
            "Статус: 🟠 Ожидает оплаты\n"
            f"Тип сообщества: {type_text}\n"
            f"Название: {html.escape(str(title))}\n"
            + post_preview
            + (f"Ссылка: {html.escape(destination)}\n" if campaign_type == "subscription" else "") +
            f"\nЗаказано {noun}: {target}\n"
            f"Цена пакета: {package_price} ⭐\n"
            f"Стоимость: {total} ⭐\n\n"
            f"Создана: {_fmt_dt(created_at)}"
        )
    elif status in {"active", "paused", "completed"}:
        progress = min(100, int(completed * 100 / target)) if target else 0
        status_text = {"active": "Выполняется", "paused": "Приостановлена", "completed": "Завершена"}[status]
        header = "в работе" if status in {"active", "paused"} else "завершена"
        text = (
            f"✅ <b>Заявка №{order_id} {header}.</b>\n\n"
            f"Статус: {status_text}\n"
            f"Тип сообщества: {type_text}\n"
            f"Название: {html.escape(str(title))}\n"
            + post_preview
            + (f"Ссылка: {html.escape(destination)}\n" if campaign_type == "subscription" else "") +
            f"\nЗаказано {noun}: {target}\n"
            f"Подтверждено: {completed}\n"
            f"Осталось: {max(0, target-completed)}\n"
            f"Прогресс: {progress}%\n\n"
            f"Размер пакета: {package_size}\n"
            f"Цена пакета: {package_price} ⭐\n"
            f"Стоимость: {total} ⭐\n\n"
            f"Создана: {_fmt_dt(created_at)}\n"
            f"Запущена: {_fmt_dt(started_at)}\n"
            f"Завершена: {_fmt_dt(completed_at)}"
        )
    else:
        status_text = {
            "pending_moderation": "⏳ Ожидает модерации",
            "rejected": "❌ Отклонена",
        }.get(status, "Неизвестный статус")
        text = (
            f"<b>Заявка №{order_id}</b>\n\n"
            f"Статус: {status_text}\n"
            f"Тип сообщества: {type_text}\n"
            f"Название: {html.escape(str(title))}\n"
            + post_preview
            + (f"Ссылка: {html.escape(destination)}\n" if campaign_type == "subscription" else "") +
            f"\nЗаказано {noun}: {target}\n"
            f"Цена пакета: {package_price} ⭐\n"
            f"Стоимость: {total} ⭐\n\n"
            f"Создана: {_fmt_dt(created_at)}"
            + (f"\n\n<b>Причина отклонения:</b> {html.escape(rejection_reason)}" if status == "rejected" and rejection_reason else "")
        )
    buttons = []
    if campaign_type == "post" and source_chat_id and source_message_id:
        buttons.append([InlineKeyboardButton(text="👁 Просмотреть пост", callback_data=f"ads_order_preview_{oid}")])
    if status == "pending_moderation":
        buttons.append([InlineKeyboardButton(text="✏️ Изменить количество", callback_data=f"ads_order_edit_{oid}")])
        buttons.append([InlineKeyboardButton(text="❌ Отменить заявку", callback_data=f"ads_order_cancel_confirm_{oid}")])
    elif status == "awaiting_payment":
        buttons.append([InlineKeyboardButton(text=f"⭐ Оплатить {total} ⭐", callback_data=f"ads_order_pay_{oid}")])
        buttons.append([InlineKeyboardButton(text="❌ Отменить заявку", callback_data=f"ads_order_cancel_confirm_{oid}")])
    elif status == "completed":
        buttons.append([InlineKeyboardButton(text="🔄 Продлить рекламу", callback_data=f"ads_order_extend_{oid}")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="ads_my_orders")])
    await _delete_current(callback.message)
    await callback.message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()


@router.callback_query(F.data.startswith("ads_order_extend_"))
async def ads_order_extend(callback: CallbackQuery, state: FSMContext):
    oid = int(callback.data.rsplit("_", 1)[1])
    row = await db.get_ad_order_for_user(oid, callback.from_user.id)
    if not row or row[2] != "completed":
        await callback.answer("Продлить можно только завершённую заявку.", show_alert=True)
        return
    await state.update_data(extend_order_id=oid, extend_campaign_type=row[1])
    await state.set_state(AdExtendOrder.waiting_quantity)
    minimum = int(await db.get_setting("ad_post_min_quantity" if row[1] == "post" else "ad_subscriber_min_quantity") or (100 if row[1] == "post" else 50))
    noun = "просмотров" if row[1] == "post" else "подписчиков"
    await _delete_current(callback.message)
    await callback.message.answer(
        f"Введите новое количество {noun}. Минимум {minimum}, количество должно быть кратно {minimum}.",
        reply_markup=_back_kb(f"ads_order_view_{oid}"),
    )
    await callback.answer()


@router.message(AdExtendOrder.waiting_quantity)
async def ads_extend_quantity(message: Message, state: FSMContext):
    data = await state.get_data()
    ctype = data.get("extend_campaign_type")
    minimum = int(await db.get_setting("ad_post_min_quantity" if ctype == "post" else "ad_subscriber_min_quantity") or (100 if ctype == "post" else 50))
    price = int(await db.get_setting("ad_post_package_price_stars" if ctype == "post" else "ad_subscriber_package_price_stars") or (150 if ctype == "post" else 100))
    value = (message.text or "").strip()
    if not value.isdigit() or int(value) < minimum or int(value) % minimum:
        await message.answer(f"Количество должно быть не меньше {minimum} и кратно {minimum}.")
        return
    quantity = int(value)
    total = quantity // minimum * price
    new_id = await db.clone_completed_ad_order(
        int(data["extend_order_id"]), message.from_user.id, quantity, minimum, price, total
    )
    await state.clear()
    if not new_id:
        await message.answer("Не удалось продлить заявку.")
        return
    await message.answer(
        f"✅ Создана новая заявка №{new_id} на основе завершённой. Она отправлена на модерацию.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📋 Мои заказы", callback_data="ads_my_orders")
        ]]),
    )
    await notify_admins_new_order(message.bot, new_id)


@router.callback_query(F.data.startswith("ads_order_preview_"))
async def ads_order_preview(callback: CallbackQuery):
    oid = int(callback.data.rsplit("_", 1)[1])
    row = await db.get_ad_order_for_user(oid, callback.from_user.id)
    if not row:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return
    source_chat_id, source_message_id = row[6], row[7]
    if row[1] != "post" or not source_chat_id or not source_message_id:
        await callback.answer("Предпросмотр поста недоступен.", show_alert=True)
        return
    delete_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Вспомнил, можно удалять", callback_data="ads_delete_post_preview")
    ]])
    try:
        await callback.bot.copy_message(
            chat_id=callback.from_user.id,
            from_chat_id=source_chat_id,
            message_id=source_message_id,
            reply_markup=delete_kb,
        )
        await callback.answer()
    except Exception:
        await callback.answer("Не удалось открыть рекламный пост.", show_alert=True)


@router.callback_query(F.data == "ads_delete_post_preview")
async def ads_delete_post_preview(callback: CallbackQuery):
    await _delete_current(callback.message)
    await callback.answer("Пост удалён.")

@router.callback_query(F.data.startswith("ads_order_edit_"))
async def ads_order_edit(callback: CallbackQuery,state:FSMContext):
    oid=int(callback.data.rsplit("_",1)[1]); row=await db.get_ad_order_for_user(oid,callback.from_user.id)
    if not row or row[2]!="pending_moderation": await callback.answer("Эту заявку уже нельзя изменить.",show_alert=True); return
    await state.update_data(edit_order_id=oid,edit_campaign_type=row[1]); await state.set_state(AdOrder.editing_quantity)
    await _delete_current(callback.message); await callback.message.answer("Введите новое количество:",reply_markup=_back_kb(f"ads_order_view_{oid}")); await callback.answer()

@router.message(AdOrder.editing_quantity)
async def ads_edit_quantity(message:Message,state:FSMContext):
    data=await state.get_data(); ctype=data["edit_campaign_type"]
    minimum=int(await db.get_setting("ad_post_min_quantity" if ctype=="post" else "ad_subscriber_min_quantity") or (100 if ctype=="post" else 50))
    price=int(await db.get_setting("ad_post_package_price_stars" if ctype=="post" else "ad_subscriber_package_price_stars") or (150 if ctype=="post" else 100))
    text=(message.text or "").strip()
    if not text.isdigit() or int(text)<minimum or int(text)%minimum: await message.answer(f"Количество должно быть не меньше {minimum} и кратно {minimum}."); return
    q=int(text); total=q//minimum*price
    ok=await db.update_pending_ad_order_quantity(data["edit_order_id"],message.from_user.id,q,minimum,price,total); await state.clear()
    await message.answer("✅ Заявка обновлена." if ok else "Заявку уже нельзя изменить.",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📋 Мои заказы",callback_data="ads_my_orders")]]))

@router.callback_query(F.data.startswith("ads_order_cancel_confirm_"))
async def ads_order_cancel_confirm(callback:CallbackQuery):
    oid=int(callback.data.rsplit("_",1)[1]); await _delete_current(callback.message)
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Да, отменить",callback_data=f"ads_order_cancel_{oid}")],[InlineKeyboardButton(text="◀️ Назад",callback_data=f"ads_order_view_{oid}")]])
    await callback.message.answer("⚠️ Отменить рекламную заявку?",reply_markup=kb); await callback.answer()

@router.callback_query(F.data.startswith("ads_order_cancel_"))
async def ads_order_cancel(callback:CallbackQuery):
    oid=int(callback.data.rsplit("_",1)[1]); ok=await db.cancel_pending_ad_order(oid,callback.from_user.id)
    await _delete_current(callback.message); await callback.message.answer("✅ Заявка отменена." if ok else "Заявку уже нельзя отменить.",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📋 Мои заказы",callback_data="ads_my_orders")]])); await callback.answer()


AD_SETTING_LABELS = {
    "ad_post_package_price_stars": "цену минимального пакета показов",
    "ad_subscriber_package_price_stars": "цену минимального пакета подписчиков",
    "ad_post_min_quantity": "минимальное количество показов",
    "ad_subscriber_min_quantity": "минимальное количество подписчиков",
}

@router.callback_query(F.data.startswith("adset_"))
async def edit_ad_setting(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    key = callback.data.removeprefix("adset_")
    if key not in AD_SETTING_LABELS:
        return
    current = await db.get_setting(key)
    await state.update_data(ad_setting_key=key)
    await state.set_state(AdAdminEdit.waiting_value)
    await callback.message.answer(f"Введите {AD_SETTING_LABELS[key]}. Текущее значение: {current}.")
    await callback.answer()

@router.message(AdAdminEdit.waiting_value)
async def save_ad_setting(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    value = (message.text or "").strip()
    if not value.isdigit() or int(value) <= 0:
        await message.answer("Введите целое положительное число.")
        return
    data = await state.get_data()
    key = data.get("ad_setting_key")
    if key not in AD_SETTING_LABELS:
        await state.clear(); return
    await db.set_setting(key, value)
    await state.clear()
    await message.answer(f"✅ Настройка сохранена: {value}.")

async def check_mandatory_subscriptions(bot, user_id: int):
    missing = []

    campaigns = await db.get_active_subscription_campaigns()

    for campaign_id, channel_ref, community_title, community_url in campaigns:
        try:
            member = await bot.get_chat_member(channel_ref, user_id)

            if member.status in {"member", "administrator", "creator"}:
                await db.confirm_sponsor_subscriber(campaign_id, user_id)
            else:
                missing.append(
                    (
                        campaign_id,
                        channel_ref,
                        community_title,
                        community_url,
                    )
                )
        except Exception:
            missing.append(
                (
                    campaign_id,
                    channel_ref,
                    community_title,
                    community_url,
                )
            )

    return missing


def mandatory_subscriptions_kb(campaigns):
    rows = []

    for _, channel_ref, community_title, community_url in campaigns:
        title = community_title or str(channel_ref)
        link = community_url

        if not link:
            channel = str(channel_ref)

            if channel.startswith("http"):
                link = channel
            elif not channel.lstrip("-").isdigit():
                link = f"https://t.me/{channel.lstrip('@')}"

        if link:
            display_title = (
                title if len(title) <= 30
                else title[:27] + "..."
            )

            rows.append([
                InlineKeyboardButton(
                    text=f"🔔 Подписаться: {display_title}",
                    url=link,
                )
            ])

    rows.append([
        InlineKeyboardButton(
            text="✅  Проверить подписки",
            callback_data="check_required_subscriptions",
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "check_required_subscriptions")
async def recheck_required_subscriptions(callback: CallbackQuery):
    missing = await check_mandatory_subscriptions(
        callback.bot,
        callback.from_user.id,
    )

    if missing:
        try:
            await callback.message.edit_reply_markup(
                reply_markup=mandatory_subscriptions_kb(missing)
            )
        except TelegramBadRequest as error:
            if "message is not modified" not in str(error):
                raise

        await callback.answer(
            "Вы ещё не подписались на все обязательные каналы.",
            show_alert=True,
        )
        return

    await callback.answer("✅ Подписки подтверждены.")

    try:
        await callback.message.delete()
    except Exception:
        pass

    welcome = (
        "👻 <b>Добро пожаловать в CASPER!</b>\n\n"
        "Я помогу вам найти нового собеседника, сыграть в мини-игры, "
        "посмотреть свою анкету и получить подарки.\n\n"
        "Выберите нужный раздел ниже 💜"
    )

    await send_brand_card(
        callback.message,
        "main_menu",
        welcome,
        main_menu(callback.from_user.id in ADMIN_IDS),
    )


AD_STATUS_LABELS = {
    "pending_moderation": "🟡 На модерации",
    "awaiting_payment": "🟠 Ожидает оплаты",
    "active": "🟢 Активна",
    "paused": "⏸ Отключена",
    "completed": "✅ Завершена",
    "rejected": "❌ Отклонена",
    "cancelled": "🚫 Отменена",
    "refunded": "↩️ Возврат",
}


def _campaign_kind(campaign_type: str, community_type: str | None = None) -> str:
    if campaign_type == "post":
        return "📢 Рекламный пост"
    return "👥 Группа" if community_type == "group" else "📣 Канал"


def _admin_campaigns_keyboard(rows) -> InlineKeyboardMarkup:
    buttons = []
    for campaign_id, campaign_type, status, completed, target, community_type, _title in rows:
        icon = {"active": "🟢", "paused": "⏸", "completed": "✅"}.get(status, "•")
        kind = "Пост" if campaign_type == "post" else ("Группа" if community_type == "group" else "Канал")
        buttons.append([InlineKeyboardButton(
            text=f"{icon} №{campaign_id} — {kind} — {completed}/{target}",
            callback_data=f"admin_ad_view:{campaign_id}",
        )])
    buttons.append([InlineKeyboardButton(text="↩️ Назад в админ-панель", callback_data="admin_back_to_panel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _show_admin_ad_list(message: Message, *, edit: bool = False):
    rows = await db.get_admin_ad_campaigns()
    counts = {"active": 0, "paused": 0, "completed": 0}
    for row in rows:
        if row[2] in counts:
            counts[row[2]] += 1
    text = (
        "📢 <b>Рекламные заявки</b>\n\n"
        f"Всего заказчиков: <b>{len(rows)}</b>\n"
        f"🟢 Активных: <b>{counts['active']}</b>\n"
        f"⏸ Отключённых: <b>{counts['paused']}</b>\n"
        f"✅ Завершённых: <b>{counts['completed']}</b>\n\n"
        "Выберите рекламную заявку:"
    )
    kb = _admin_campaigns_keyboard(rows)
    if edit:
        await message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.message(F.text == "📢 Реклама")
async def admin_advertising_panel(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    await _show_admin_ad_list(message)


@router.callback_query(F.data == "admin_ads_list")
async def admin_ads_list_callback(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await _show_admin_ad_list(callback.message, edit=True)
    await callback.answer()


async def _render_admin_campaign(campaign_id: int):
    row = await db.get_admin_ad_campaign(campaign_id)
    if not row:
        return None, None
    (cid, advertiser_id, campaign_type, status, target, completed, package_size,
     package_price, total_price, source_chat_id, source_message_id, channel_ref,
     community_type, community_title, community_url, created_at, started_at, completed_at) = row
    remaining = max(target - completed, 0)
    progress = min(100, round(completed * 100 / target)) if target else 0
    kind = _campaign_kind(campaign_type, community_type)
    unit_ordered = "показов" if campaign_type == "post" else ("участников" if community_type == "group" else "подписчиков")
    done_label = "Выполнено" if campaign_type == "post" else "Подтверждено"
    extra = ""
    if campaign_type == "subscription":
        extra = (
            f"\nТип сообщества: <b>{'👥 Группа' if community_type == 'group' else '📢 Канал'}</b>"
            f"\nНазвание: <b>{html.escape(community_title or 'Не указано')}</b>"
            f"\nИдентификатор: <code>{html.escape(str(channel_ref or '—'))}</code>\n"
        )
    text = (
        f"{kind} <b>№{cid}</b>\n\n"
        f"Статус: <b>{AD_STATUS_LABELS.get(status, status)}</b>\n"
        f"Рекламодатель: <code>{advertiser_id}</code>\n"
        f"{extra}\n"
        f"Заказано {unit_ordered}: <b>{target}</b>\n"
        f"{done_label}: <b>{completed}</b>\n"
        f"Осталось: <b>{remaining}</b>\n"
        f"Прогресс: <b>{progress}%</b>\n\n"
        f"Размер пакета: <b>{package_size}</b>\n"
        f"Цена пакета: <b>{package_price} ⭐</b>\n"
        f"Стоимость: <b>{total_price} ⭐</b>\n\n"
        + ("✅ <b>Реклама оплачена и работает.</b>\n\n" if status == "active" else "")
        + f"Создана: <code>{created_at or '—'}</code>\n"
        f"Запущена: <code>{started_at or '—'}</code>\n"
        f"Завершена: <code>{completed_at or '—'}</code>"
    )
    buttons = []
    if campaign_type == "post" and source_chat_id and source_message_id:
        buttons.append([InlineKeyboardButton(text="👁 Посмотреть рекламный пост", callback_data=f"admin_ad_preview:{cid}")])
    elif campaign_type == "subscription" and community_url:
        buttons.append([InlineKeyboardButton(text="🔗 Открыть сообщество", url=community_url)])
    if status == "pending_moderation":
        buttons.append([
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"ads_approve_{cid}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"ads_reject_{cid}"),
        ])
    elif status == "active":
        buttons.append([InlineKeyboardButton(text="⛔ Отключить рекламу", callback_data=f"admin_ad_pause_confirm:{cid}")])
    elif status == "paused" and completed < target:
        buttons.append([InlineKeyboardButton(text="▶️ Включить рекламу", callback_data=f"admin_ad_resume:{cid}")])
    if status != "active":
        buttons.append([InlineKeyboardButton(text="🗑 Удалить зависшую заявку", callback_data=f"admin_ad_delete_confirm:{cid}")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад к списку рекламы", callback_data="admin_ads_list")])
    return text, InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data.startswith("admin_ad_view:"))
async def admin_ad_view(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    campaign_id = int(callback.data.split(":", 1)[1])
    text, kb = await _render_admin_campaign(campaign_id)
    if not text:
        await callback.answer("Кампания не найдена.", show_alert=True)
        return
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_ad_preview:"))
async def admin_ad_preview(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    campaign_id = int(callback.data.split(":", 1)[1])
    row = await db.get_admin_ad_campaign(campaign_id)
    if not row or not row[9] or not row[10]:
        await callback.answer("Рекламный пост недоступен.", show_alert=True)
        return
    try:
        await callback.bot.copy_message(callback.from_user.id, row[9], row[10])
        await callback.answer("Пост отправлен вам в личные сообщения.")
    except Exception:
        await callback.answer("Не удалось показать пост.", show_alert=True)


@router.callback_query(F.data.startswith("admin_ad_pause_confirm:"))
async def admin_ad_pause_confirm(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    campaign_id = int(callback.data.split(":", 1)[1])
    row = await db.get_admin_ad_campaign(campaign_id)
    if not row or row[3] != "active":
        await callback.answer("Кампания уже не активна.", show_alert=True)
        return
    remaining = max(row[4] - row[5], 0)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, отключить", callback_data=f"admin_ad_pause:{campaign_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin_ad_view:{campaign_id}")],
    ])
    await callback.message.edit_text(
        f"⚠️ <b>Отключить рекламную кампанию №{campaign_id}?</b>\n\n"
        "Реклама перестанет участвовать в показах или обязательных подписках.\n"
        f"Выполнено: <b>{row[5]}</b>\nОсталось: <b>{remaining}</b>",
        parse_mode="HTML", reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_ad_pause:"))
async def admin_ad_pause(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    campaign_id = int(callback.data.split(":", 1)[1])
    changed = await db.set_ad_campaign_paused(campaign_id, True)
    if not changed:
        await callback.answer("Не удалось отключить кампанию.", show_alert=True)
        return
    text, kb = await _render_admin_campaign(campaign_id)
    await callback.message.edit_text("✅ Кампания отключена.\n\n" + text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_ad_resume:"))
async def admin_ad_resume(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    campaign_id = int(callback.data.split(":", 1)[1])
    changed = await db.set_ad_campaign_paused(campaign_id, False)
    if not changed:
        await callback.answer("Не удалось включить кампанию.", show_alert=True)
        return
    text, kb = await _render_admin_campaign(campaign_id)
    await callback.message.edit_text("✅ Кампания снова активна.\n\n" + text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_ad_delete_confirm:"))
async def admin_ad_delete_confirm(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    campaign_id = int(callback.data.split(":", 1)[1])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"admin_ad_delete:{campaign_id}")],
        [InlineKeyboardButton(text="◀️ Отмена", callback_data=f"admin_ad_view:{campaign_id}")],
    ])
    await callback.message.edit_text(
        f"🗑 <b>Удалить рекламную заявку №{campaign_id}?</b>\n\n"
        "Заявка и связанные с ней служебные данные будут удалены из базы без возможности восстановления.",
        parse_mode="HTML",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_ad_delete:"))
async def admin_ad_delete(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    campaign_id = int(callback.data.split(":", 1)[1])
    deleted = await db.delete_ad_campaign(campaign_id)
    await callback.answer("Заявка удалена" if deleted else "Заявка не найдена", show_alert=True)
    await _show_admin_ad_list(callback.message, edit=True)

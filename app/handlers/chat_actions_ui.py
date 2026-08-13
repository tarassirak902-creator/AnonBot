from __future__ import annotations

from aiogram import F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, Message

from . import shared


@shared.router.message(F.text.in_({"🎁 Подарок", "🎁 Подарить подарок"}))
async def show_gifts(message: Message, skip_dialog_check: bool = False) -> None:
    user_id = message.from_user.id
    if not skip_dialog_check and not await shared.db.get_partner(user_id):
        await message.answer("Вы не находитесь в диалоге.")
        return

    gifts = await shared.db.get_all_gifts()
    if not gifts:
        await message.answer("Нет доступных подарков.")
        return

    is_vip = await shared.db.is_user_vip(user_id)
    keyboard: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for gift_id, name, emoji, price in gifts:
        actual_price = int(price * 0.7) if is_vip else price
        price_text = f"{actual_price} ⭐ (-30%)" if is_vip else f"{price} ⭐"
        row.append(InlineKeyboardButton(
            text=f"{emoji} {name} — {price_text}",
            callback_data=f"buy_gift_{gift_id}",
        ))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(text="не заслужила😜", callback_data="close_gifts_menu")])

    await message.answer(
        "🎁 Выберите подарок для собеседника:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
    )


@shared.router.message(F.text.in_({"👤 Раскрыть", "👤 Кто это?", "⭐ Кто собеседник"}))
async def reveal_partner(message: Message) -> None:
    partner_id = await shared.db.get_partner(message.from_user.id)
    if not partner_id:
        await message.answer("Вы не находитесь в диалоге.")
        return

    cost = int(await shared.db.get_setting("reveal_cost"))
    pay_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Узнать за {cost} ⭐", pay=True)],
        [InlineKeyboardButton(text="↩️ Назад в диалог", callback_data="reveal_back_to_chat")],
    ])
    await message.answer_invoice(
        title="Узнать собеседника",
        description="Раскрыть имя, username и Telegram ID собеседника.",
        payload=f"reveal_{partner_id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Раскрытие личности", amount=cost)],
        start_parameter="reveal",
        reply_markup=pay_kb,
    )


@shared.router.message(F.text.in_({"🚨 Жалоба", "⚠️ Пожаловаться"}))
async def complaint_menu(message: Message) -> None:
    if not await shared.db.get_partner(message.from_user.id):
        await message.answer("Вы не в диалоге.")
        return
    await message.answer(
        "Выберите причину жалобы:",
        reply_markup=shared.complaint_reasons(),
    )

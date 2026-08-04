from __future__ import annotations

import logging

from aiogram import F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from app import database as db
from app.core.games import GAME_NAMES
from app.handlers.shared import router

logger = logging.getLogger(__name__)


@router.message(F.successful_payment.invoice_payload.startswith("duel_create_"))
async def successful_duel_creation_payment(message: Message) -> None:
    payment = message.successful_payment
    creator_id = message.from_user.id
    try:
        parts = payment.invoice_payload.split("_")
        partner_id = int(parts[2])
        amount = int(parts[3])
        game_type = parts[4]
    except (AttributeError, IndexError, TypeError, ValueError):
        await message.answer(
            "Платёж получен, но данные дуэли повреждены. Обратитесь в /paysupport."
        )
        return

    if amount != int(payment.total_amount) or game_type not in GAME_NAMES:
        await message.answer(
            "Платёж получен, но параметры дуэли изменились. Обратитесь в /paysupport."
        )
        return

    duel_id = await db.create_waiting_duel_from_payment(
        charge_id=payment.telegram_payment_charge_id,
        creator_id=creator_id,
        partner_id=partner_id,
        amount=amount,
        game_type=game_type,
    )
    if duel_id is None:
        logger.warning(
            "Duel creation rejected after payment: charge_id=%s creator=%s partner=%s",
            payment.telegram_payment_charge_id,
            creator_id,
            partner_id,
        )
        await message.answer(
            "Платёж зарегистрирован, но диалог уже завершён или другая дуэль активна. "
            "Обратитесь в /paysupport."
        )
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text=f"✅ Принять и оплатить {amount} ⭐",
                callback_data=f"pay_duel_accept_{duel_id}",
            ),
            InlineKeyboardButton(
                text="❌ Отклонить",
                callback_data=f"decline_duel_{duel_id}",
            ),
        ]]
    )
    game_title = GAME_NAMES.get(game_type, "Дуэль")
    try:
        await message.bot.send_message(
            partner_id,
            f"⚔️ <b>Собеседник вызывает вас на дуэль «{game_title}»!</b>\n\n"
            f"Ставка каждого игрока: <b>{amount} ⭐</b>.",
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    except Exception:
        logger.exception(
            "Could not notify duel partner: duel_id=%s partner_id=%s",
            duel_id,
            partner_id,
        )
        await message.answer(
            "Ставка сохранена, но уведомление собеседнику не доставлено. "
            "Обратитесь в /paysupport."
        )
        return

    await message.answer(
        f"⏳ Ваша ставка <b>{amount} ⭐</b> оплачена. Ожидаем ответ собеседника.",
        parse_mode="HTML",
    )

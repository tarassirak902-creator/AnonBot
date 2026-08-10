from __future__ import annotations

import logging

from aiogram import F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from app import database as db
from app.core.payment_middleware import payment_reconciliation_required
from app.handlers.shared import ADMIN_IDS, router

logger = logging.getLogger(__name__)


@router.message(F.successful_payment.invoice_payload.startswith("ad_order_"))
async def successful_ad_order_payment(message: Message):
    payment = message.successful_payment
    user_id = message.from_user.id
    try:
        order_id = int(payment.invoice_payload.rsplit("_", 1)[1])
    except (AttributeError, IndexError, TypeError, ValueError):
        await message.answer(
            "Платёж получен, но данные рекламного заказа повреждены. Обратитесь в /paysupport."
        )
        return payment_reconciliation_required("advertising order payload became invalid after payment")

    activated = await db.activate_ad_order(
        order_id,
        user_id,
        payment.telegram_payment_charge_id,
    )
    if not activated:
        await message.answer(
            "Платёж получен, но заявка уже была активирована или недоступна. Обратитесь в /paysupport."
        )
        return payment_reconciliation_required("paid advertising order could not be activated")

    await message.answer(
        f"✅ <b>Рекламная кампания №{order_id} оплачена и автоматически запущена.</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="👁 Открыть заказ", callback_data=f"ads_order_view_{order_id}")],
                [InlineKeyboardButton(text="📋 Мои заказы", callback_data="ads_my_orders")],
            ]
        ),
    )
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                f"✅ Реклама по заявке №{order_id} оплачена и работает.",
            )
        except Exception:
            logger.exception(
                "Не удалось уведомить администратора об оплате рекламы: "
                "admin_id=%s order_id=%s user_id=%s",
                admin_id,
                order_id,
                user_id,
            )
    return None

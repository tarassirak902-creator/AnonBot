from __future__ import annotations

from html import escape
import logging

from aiogram import F
from aiogram.types import Message

from app import database as db
from app.core.payment_middleware import payment_reconciliation_required
from app.handlers.shared import router

logger = logging.getLogger(__name__)


@router.message(F.successful_payment.invoice_payload.startswith("reveal_"))
async def successful_chat_reveal_payment(message: Message):
    payment = message.successful_payment
    user_id = message.from_user.id
    try:
        partner_id = int(payment.invoice_payload.split("_", 1)[1])
        amount = int(payment.total_amount)
    except (AttributeError, TypeError, ValueError):
        await message.answer(
            "Платёж получен, но данные раскрытия повреждены. Обратитесь в /paysupport."
        )
        return payment_reconciliation_required("chat reveal payload became invalid after payment")

    try:
        applied = await db.apply_chat_reveal_payment(
            charge_id=payment.telegram_payment_charge_id,
            buyer_id=user_id,
            partner_id=partner_id,
            amount=amount,
        )
    except ValueError as exc:
        logger.warning(
            "Paid chat reveal could not be applied: user_id=%s partner_id=%s reason=%s",
            user_id,
            partner_id,
            exc,
        )
        await message.answer(
            "Платёж получен, но предложение раскрытия уже устарело. Обратитесь в /paysupport."
        )
        return payment_reconciliation_required("paid chat reveal could not be applied")

    if not applied:
        return None

    try:
        partner = await message.bot.get_chat(partner_id)
        full_name = f"{partner.first_name or ''} {partner.last_name or ''}".strip() or "Не указано"
        username = f"@{partner.username}" if partner.username else "Не установлен"
        text = (
            "✅ <b>Ваш прошлый собеседник раскрыт</b>\n\n"
            f"Имя: <b>{escape(full_name)}</b>\n"
            f"Username: <b>{escape(username)}</b>\n"
            f"Telegram ID: <code>{partner_id}</code>\n\n"
            f'<a href="tg://user?id={partner_id}">Открыть профиль</a>'
        )
    except Exception:
        logger.exception("Could not resolve revealed chat partner: partner_id=%s", partner_id)
        text = (
            "✅ <b>Ваш прошлый собеседник раскрыт</b>\n\n"
            f"Telegram ID: <code>{partner_id}</code>\n"
            f'<a href="tg://user?id={partner_id}">Открыть профиль</a>'
        )

    await message.answer(text, parse_mode="HTML")
    return None

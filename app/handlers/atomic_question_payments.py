from __future__ import annotations

import logging

from aiogram import F
from aiogram.types import Message

from app import database as db
from app.handlers.shared import router

logger = logging.getLogger(__name__)


async def _resolve_receiver(user_id: int, context: str, reference: str) -> int | None:
    if context == "t":
        try:
            receiver_id = int(reference)
        except (TypeError, ValueError):
            return None
        if receiver_id == user_id or not await db.get_question_owner_by_id(receiver_id):
            return None
        return receiver_id

    if context not in {"q", "a"}:
        return None
    question = await db.get_question_by_public_id(reference)
    if not question:
        return None
    if context == "q" and int(question[3]) == user_id:
        return int(question[2])
    if context == "a" and int(question[2]) == user_id:
        return int(question[3])
    return None


@router.message(F.successful_payment.invoice_payload.startswith("question_stars:"))
async def successful_question_stars_payment(message: Message) -> None:
    payment = message.successful_payment
    user_id = message.from_user.id
    try:
        _, context, reference, amount_raw = payment.invoice_payload.split(":", 3)
        amount = int(amount_raw)
        receiver_id = await _resolve_receiver(user_id, context, reference)
    except (AttributeError, TypeError, ValueError):
        receiver_id = None
        amount = 0

    if not receiver_id or amount != int(payment.total_amount) or not 1 <= amount <= 10_000:
        await db.log_action(user_id, "question_stars_invalid", payment.invoice_payload)
        await message.answer("Платёж получен, но данные перевода повреждены. Обратитесь в /paysupport.")
        return

    applied = await db.apply_question_stars_payment(
        charge_id=payment.telegram_payment_charge_id,
        buyer_id=user_id,
        receiver_id=receiver_id,
        amount=amount,
    )
    if not applied:
        logger.warning(
            "Question Stars charge already applied: charge_id=%s user_id=%s",
            payment.telegram_payment_charge_id,
            user_id,
        )
        return

    try:
        await message.bot.send_message(
            receiver_id,
            "⭐ <b>Вам анонимно подарили звёзды!</b>\n\n"
            "Источник:\n❓ Анонимные вопросы\n\n"
            f"Количество: <b>{amount} ⭐</b>",
            parse_mode="HTML",
        )
    except Exception:
        logger.exception(
            "Не удалось уведомить получателя Stars: receiver_id=%s charge_id=%s",
            receiver_id,
            payment.telegram_payment_charge_id,
        )

    await message.answer(
        "✅ <b>Звёзды успешно отправлены!</b>\n\nВаше имя осталось анонимным.",
        parse_mode="HTML",
    )


@router.message(F.successful_payment.invoice_payload.startswith("question_vip:"))
async def successful_question_vip_payment(message: Message) -> None:
    payment = message.successful_payment
    user_id = message.from_user.id
    try:
        _, context, reference, days_raw = payment.invoice_payload.split(":", 3)
        days = int(days_raw)
        receiver_id = await _resolve_receiver(user_id, context, reference)
    except (AttributeError, TypeError, ValueError):
        receiver_id = None
        days = 0

    amount = int(payment.total_amount)
    if not receiver_id or days != 30 or amount != 100:
        await db.log_action(user_id, "question_vip_invalid", payment.invoice_payload)
        await message.answer("Платёж получен, но данные VIP повреждены. Обратитесь в /paysupport.")
        return

    applied = await db.apply_vip_payment(
        charge_id=payment.telegram_payment_charge_id,
        buyer_id=user_id,
        receiver_id=receiver_id,
        amount=amount,
        days=days,
        purchase_type="question_vip",
    )
    if not applied:
        logger.warning(
            "Question VIP charge already applied: charge_id=%s user_id=%s",
            payment.telegram_payment_charge_id,
            user_id,
        )
        return

    try:
        await message.bot.send_message(
            receiver_id,
            "👑 <b>Вам анонимно подарили VIP статус!</b>\n\n"
            "Источник:\n❓ Анонимные вопросы\n\n"
            f"Срок: <b>{days} дней</b>",
            parse_mode="HTML",
        )
    except Exception:
        logger.exception(
            "Не удалось уведомить получателя VIP: receiver_id=%s charge_id=%s",
            receiver_id,
            payment.telegram_payment_charge_id,
        )

    await message.answer(
        "✅ <b>VIP статус успешно подарен!</b>\n\nВаше имя осталось анонимным.",
        parse_mode="HTML",
    )

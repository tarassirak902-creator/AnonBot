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


@router.message(F.successful_payment.invoice_payload.startswith("question_premium:"))
async def successful_question_premium_payment(message: Message) -> None:
    payment = message.successful_payment
    user_id = message.from_user.id
    payload = payment.invoice_payload
    charge_id = payment.telegram_payment_charge_id

    try:
        _, context, reference, months_raw, stars_raw = payload.split(":", 4)
        months = int(months_raw)
        stars = int(stars_raw)
        receiver_id = await _resolve_receiver(user_id, context, reference)
    except (AttributeError, TypeError, ValueError):
        months = stars = 0
        receiver_id = None

    allowed = {3: 1000, 6: 1500, 12: 2500}
    if not receiver_id or allowed.get(months) != stars or int(payment.total_amount) != stars:
        await db.log_action(user_id, "question_premium_invalid", payload)
        await message.answer(
            "Платёж получен, но данные Telegram Premium повреждены. Обратитесь в /paysupport."
        )
        return

    status = await db.register_premium_delivery(
        charge_id=charge_id,
        buyer_id=user_id,
        receiver_id=receiver_id,
        months=months,
        stars=stars,
        payload=payload,
    )
    if status in {"delivered", "failed", "delivering"}:
        logger.warning(
            "Premium charge is not eligible for automatic retry: charge_id=%s status=%s",
            charge_id,
            status,
        )
        if status == "failed":
            await message.answer(
                "Платёж уже зарегистрирован, но автоматическая выдача Premium завершилась ошибкой. "
                "Обратитесь в /paysupport."
            )
        return

    if not await db.claim_premium_delivery(charge_id):
        logger.warning("Premium delivery already claimed: charge_id=%s", charge_id)
        return

    try:
        await message.bot.gift_premium_subscription(
            user_id=receiver_id,
            month_count=months,
            star_count=stars,
            text="Анонимный подарок через вопросы Casper 💜",
        )
    except Exception as exc:
        logger.exception(
            "Telegram Premium delivery failed: charge_id=%s receiver_id=%s",
            charge_id,
            receiver_id,
        )
        await db.mark_premium_delivery_failed(charge_id, repr(exc))
        await message.answer(
            "Оплата прошла, но Telegram Premium не удалось выдать автоматически. "
            "Повторная выдача заблокирована для защиты от дубля. Обратитесь в /paysupport."
        )
        return

    completed = await db.complete_premium_delivery(charge_id)
    if not completed:
        logger.critical(
            "Premium was delivered by Telegram but database finalization failed: charge_id=%s",
            charge_id,
        )
        await message.answer(
            "Telegram Premium выдан, но внутреннюю запись не удалось завершить. "
            "Обратитесь в /paysupport и сообщите время платежа."
        )
        return

    try:
        await message.bot.send_message(
            receiver_id,
            "💎 <b>Вам анонимно подарили Telegram Premium!</b>\n\n"
            "Источник:\n❓ Анонимные вопросы\n\n"
            f"Срок: <b>{months} месяцев</b>",
            parse_mode="HTML",
        )
    except Exception:
        logger.exception(
            "Не удалось уведомить получателя Premium: charge_id=%s receiver_id=%s",
            charge_id,
            receiver_id,
        )

    await message.answer(
        "✅ <b>Telegram Premium успешно подарен!</b>\n\nВаше имя осталось анонимным.",
        parse_mode="HTML",
    )

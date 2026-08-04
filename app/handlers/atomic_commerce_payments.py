from __future__ import annotations

import logging

from aiogram import F
from aiogram.types import Message

from app import database as db
from app.handlers.shared import router

logger = logging.getLogger(__name__)


async def _resolve_question_receiver(user_id: int, context: str, reference: str) -> int | None:
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


async def _notify_gift(message: Message, receiver_id: int, amount: int, source: str) -> None:
    try:
        await message.bot.send_message(
            receiver_id,
            "🎁 <b>Вам анонимно подарили подарок!</b>\n\n"
            f"Источник:\n{source}\n\n"
            f"Стоимость: <b>{amount} ⭐</b>",
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("Gift notification failed: receiver_id=%s", receiver_id)


@router.message(F.successful_payment.invoice_payload.startswith("question_gift:"))
async def successful_question_gift_payment(message: Message) -> None:
    payment = message.successful_payment
    buyer_id = message.from_user.id
    try:
        _, context, reference, gift_raw = payment.invoice_payload.split(":", 3)
        gift_id = int(gift_raw)
        amount = int(payment.total_amount)
    except (AttributeError, TypeError, ValueError):
        await message.answer("Платёж получен, но данные подарка повреждены. Обратитесь в /paysupport.")
        return

    receiver_id = await _resolve_question_receiver(buyer_id, context, reference)
    if not receiver_id or not await db.get_gift(gift_id):
        await message.answer("Платёж получен, но подарок или получатель недоступен. Обратитесь в /paysupport.")
        return

    applied = await db.apply_gift_payment(
        charge_id=payment.telegram_payment_charge_id,
        buyer_id=buyer_id,
        receiver_id=receiver_id,
        gift_id=gift_id,
        amount=amount,
        purchase_type="question_gift",
    )
    if not applied:
        return
    await _notify_gift(message, receiver_id, amount, "❓ Анонимные вопросы")
    await message.answer(
        "✅ <b>Подарок успешно отправлен!</b>\n\nВаше имя осталось анонимным.",
        parse_mode="HTML",
    )


@router.message(F.successful_payment.invoice_payload.startswith("gift_"))
async def successful_chat_gift_payment(message: Message) -> None:
    payment = message.successful_payment
    buyer_id = message.from_user.id
    try:
        _, gift_raw, receiver_raw = payment.invoice_payload.split("_", 2)
        gift_id = int(gift_raw)
        receiver_id = int(receiver_raw)
        amount = int(payment.total_amount)
    except (AttributeError, TypeError, ValueError):
        await message.answer("Платёж получен, но данные подарка повреждены. Обратитесь в /paysupport.")
        return

    if receiver_id == buyer_id or not await db.get_gift(gift_id):
        await message.answer("Платёж получен, но подарок или получатель недоступен. Обратитесь в /paysupport.")
        return

    applied = await db.apply_gift_payment(
        charge_id=payment.telegram_payment_charge_id,
        buyer_id=buyer_id,
        receiver_id=receiver_id,
        gift_id=gift_id,
        amount=amount,
        purchase_type="gift",
    )
    if not applied:
        return
    await _notify_gift(message, receiver_id, amount, "💬 Анонимный чат")
    await message.answer("✅ <b>Подарок успешно отправлен.</b>", parse_mode="HTML")


@router.message(F.successful_payment.invoice_payload.startswith("question_reveal:"))
async def successful_question_reveal_payment(message: Message) -> None:
    payment = message.successful_payment
    buyer_id = message.from_user.id
    public_id = payment.invoice_payload.split(":", 1)[1]
    try:
        sender_id = await db.apply_question_reveal_payment(
            charge_id=payment.telegram_payment_charge_id,
            buyer_id=buyer_id,
            public_id=public_id,
            amount=int(payment.total_amount),
        )
    except ValueError:
        logger.exception("Question reveal payment could not be applied: public_id=%s", public_id)
        await message.answer("Платёж получен, но вопрос уже раскрыт или недоступен. Обратитесь в /paysupport.")
        return
    if sender_id is None:
        return

    try:
        author = await message.bot.get_chat(sender_id)
        full_name = f"{author.first_name or ''} {author.last_name or ''}".strip() or "Не указано"
        username = f"@{author.username}" if author.username else "Не установлен"
        text = (
            "✅ <b>Автор вопроса раскрыт</b>\n\n"
            f"Имя: <b>{full_name}</b>\n"
            f"Username: <b>{username}</b>\n"
            f"Telegram ID: <code>{author.id}</code>\n\n"
            f'<a href="tg://user?id={author.id}">Открыть профиль</a>'
        )
    except Exception:
        logger.exception("Could not resolve revealed question author: sender_id=%s", sender_id)
        text = f'✅ Автор раскрыт: <a href="tg://user?id={sender_id}">открыть профиль</a>'
    await message.answer(text, parse_mode="HTML")


@router.message(F.successful_payment.invoice_payload == "vip_subscription_100")
async def successful_self_vip_payment(message: Message) -> None:
    payment = message.successful_payment
    user_id = message.from_user.id
    applied = await db.apply_vip_payment(
        charge_id=payment.telegram_payment_charge_id,
        buyer_id=user_id,
        receiver_id=user_id,
        amount=int(payment.total_amount),
        days=30,
        purchase_type="vip_subscription",
    )
    if not applied:
        return
    await message.answer(
        "👑 <b>VIP подписка активирована или продлена на 30 дней!</b>",
        parse_mode="HTML",
    )

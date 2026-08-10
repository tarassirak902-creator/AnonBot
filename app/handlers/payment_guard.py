from __future__ import annotations

from aiogram.types import PreCheckoutQuery

from app import database as db
from app.core.games import GAME_NAMES
from app.handlers.shared import router

_MAX_STARS = 10_000


async def _resolve_question_receiver(user_id: int, context: str, reference: str) -> int | None:
    if context == "t":
        try:
            candidate = int(reference)
        except (TypeError, ValueError):
            return None
        if candidate == user_id or not await db.get_question_owner_by_id(candidate):
            return None
        return candidate

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


async def _validate_payload(user_id: int, payload: str, total_amount: int) -> str | None:
    """Возвращает текст ошибки или ``None``, если счёт допустим."""
    if total_amount < 1 or total_amount > _MAX_STARS:
        return "Недопустимая сумма платежа. Создайте счёт заново."

    try:
        if payload == "vip_subscription_100":
            return None if total_amount == 100 else "Стоимость VIP изменилась. Создайте счёт заново."

        if payload.startswith("question_stars:"):
            _, context, reference, amount_raw = payload.split(":", 3)
            amount = int(amount_raw)
            receiver = await _resolve_question_receiver(user_id, context, reference)
            if not receiver or amount != total_amount or not 1 <= amount <= _MAX_STARS:
                return "Данные перевода звёзд устарели. Создайте счёт заново."
            return None

        if payload.startswith("question_premium:"):
            _, context, reference, months_raw, stars_raw = payload.split(":", 4)
            months, stars = int(months_raw), int(stars_raw)
            allowed = {3: 1000, 6: 1500, 12: 2500}
            receiver = await _resolve_question_receiver(user_id, context, reference)
            if not receiver or allowed.get(months) != stars or total_amount != stars:
                return "Вариант Telegram Premium устарел. Создайте счёт заново."
            return None

        if payload.startswith("question_vip:"):
            _, context, reference, days_raw = payload.split(":", 3)
            receiver = await _resolve_question_receiver(user_id, context, reference)
            if not receiver or int(days_raw) != 30 or total_amount != 100:
                return "Данные подарочного VIP устарели. Создайте счёт заново."
            return None

        if payload.startswith("question_reveal:"):
            public_id = payload.split(":", 1)[1]
            question = await db.get_question_by_public_id(public_id)
            if (
                not question
                or int(question[3]) != user_id
                or bool(question[10])
                or total_amount != 100
            ):
                return "Вопрос недоступен, автор уже раскрыт или стоимость изменилась."
            return None

        if payload.startswith("question_gift:"):
            _, context, reference, gift_id_raw = payload.split(":", 3)
            receiver = await _resolve_question_receiver(user_id, context, reference)
            gift = await db.get_gift(int(gift_id_raw))
            if not receiver or not gift:
                return "Подарок или получатель больше недоступны."
            expected = int(gift[2] * 0.7) if await db.is_user_vip(user_id) else int(gift[2])
            if total_amount != expected:
                return "Стоимость подарка изменилась. Создайте счёт заново."
            return None

        if payload.startswith("gift_"):
            _, gift_id_raw, receiver_id_raw = payload.split("_", 2)
            gift = await db.get_gift(int(gift_id_raw))
            receiver_id = int(receiver_id_raw)
            if not gift or receiver_id == user_id:
                return "Подарок или получатель больше недоступны."
            current_partner = await db.get_partner(user_id)
            if current_partner != receiver_id:
                return "Анонимный диалог уже завершён. Создайте счёт заново."
            expected = int(gift[2] * 0.7) if await db.is_user_vip(user_id) else int(gift[2])
            if total_amount != expected:
                return "Стоимость подарка изменилась. Создайте счёт заново."
            return None

        if payload.startswith("reveal_"):
            partner_id = int(payload.split("_", 1)[1])
            expected = int(await db.get_setting("reveal_cost"))
            if (
                partner_id == user_id
                or not await db.is_latest_partner(user_id, partner_id)
                or total_amount != expected
            ):
                return "Предложение раскрытия устарело или стоимость изменилась."
            return None

        if payload.startswith("solo_"):
            _, game_type, bet_raw = payload.split("_", 2)
            bet = int(bet_raw)
            if game_type not in GAME_NAMES or bet != total_amount or not 1 <= bet <= _MAX_STARS:
                return "Некорректная игровая ставка. Создайте счёт заново."
            return None

        if payload.startswith("duel_create_"):
            parts = payload.split("_")
            if len(parts) < 5:
                return "Повреждены данные дуэли."
            partner_id, bet = int(parts[2]), int(parts[3])
            game_type = parts[4]
            current_partner = await db.get_partner(user_id)
            if (
                partner_id == user_id
                or current_partner != partner_id
                or game_type not in GAME_NAMES
                or bet != total_amount
                or not 1 <= bet <= _MAX_STARS
            ):
                return "Некорректная или устаревшая дуэль. Создайте счёт заново."
            return None

        if payload.startswith("duel_accept_"):
            duel_id = int(payload.split("_")[2])
            duel = await db.get_game_duel(duel_id)
            if not duel or duel[4] != "waiting":
                return "Эта дуэль уже недоступна."
            if int(duel[2]) != user_id or int(duel[3]) != total_amount:
                return "Счёт дуэли не принадлежит вам или ставка изменилась."
            return None

        if payload.startswith("ad_order_"):
            order_id = int(payload.rsplit("_", 1)[1])
            order = await db.get_ad_order_for_user(order_id, user_id)
            if not order or order[2] != "awaiting_payment" or int(order[5]) != total_amount:
                return "Рекламный заказ недоступен или его стоимость изменилась."
            return None

    except (TypeError, ValueError, IndexError):
        return "Счёт повреждён. Создайте его заново."

    return "Неизвестный тип платежа. Создайте счёт заново."


@router.pre_checkout_query()
async def validate_pre_checkout(pre_checkout: PreCheckoutQuery) -> None:
    if pre_checkout.currency != "XTR":
        await pre_checkout.answer(ok=False, error_message="Поддерживаются только Telegram Stars.")
        return

    error = await _validate_payload(
        pre_checkout.from_user.id,
        pre_checkout.invoice_payload,
        int(pre_checkout.total_amount),
    )
    if error:
        await pre_checkout.answer(ok=False, error_message=error)
        return

    await pre_checkout.answer(ok=True)

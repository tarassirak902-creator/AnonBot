from __future__ import annotations

import asyncio
import logging

from aiogram import F
from aiogram.types import Message

from app import database as db
from app.core.games import GAME_NAMES, TELEGRAM_DICE_EMOJIS, play_custom_duel
from app.handlers.shared import router

logger = logging.getLogger(__name__)


async def _safe_send(bot, user_id: int, text: str) -> None:
    try:
        await bot.send_message(user_id, text, parse_mode="HTML")
    except Exception:
        logger.exception("Не удалось отправить результат дуэли: user_id=%s", user_id)


@router.message(F.successful_payment.invoice_payload.startswith("duel_accept_"))
async def successful_duel_accept_payment(message: Message) -> None:
    """Handle the second duel payment with atomic state and balance changes."""
    payment = message.successful_payment
    user_id = message.from_user.id

    try:
        duel_id = int(payment.invoice_payload.split("_")[2])
        paid_amount = int(payment.total_amount)
    except (AttributeError, IndexError, TypeError, ValueError):
        await message.answer("Платёж получен, но данные дуэли повреждены. Обратитесь в /paysupport.")
        return

    duel = await db.claim_waiting_duel(duel_id, user_id, paid_amount)
    if duel is None:
        await message.answer("Эта дуэль уже была обработана или больше недоступна.")
        return

    _, creator_id, partner_id, bet, _, game_type = duel
    creator_id = int(creator_id)
    partner_id = int(partner_id)
    bet = int(bet)
    game_type = game_type or "darts"
    game_title = GAME_NAMES.get(game_type, "Дуэль")
    bot = message.bot

    await _safe_send(
        bot,
        creator_id,
        f"🚀 <b>Дуэль «{game_title}» началась!</b>\nОбе ставки по {bet} ⭐ оплачены.",
    )
    await _safe_send(
        bot,
        partner_id,
        f"🚀 <b>Дуэль «{game_title}» началась!</b>\nОбе ставки по {bet} ⭐ оплачены.",
    )

    try:
        if game_type in TELEGRAM_DICE_EMOJIS:
            emoji = TELEGRAM_DICE_EMOJIS[game_type]
            first = await bot.send_dice(creator_id, emoji=emoji)
            second = await bot.send_dice(partner_id, emoji=emoji)
            await asyncio.sleep(4)
            value_creator = int(first.dice.value)
            value_partner = int(second.dice.value)
            result_text = f"Результаты: <b>{value_creator}</b> против <b>{value_partner}</b>."
        else:
            value_creator, value_partner, result_text = play_custom_duel(game_type)

        if value_creator > value_partner:
            winner_id = creator_id
        elif value_partner > value_creator:
            winner_id = partner_id
        else:
            winner_id = None

        credited = await db.settle_active_duel(duel_id, winner_id)
        if credited is None:
            logger.error("Дуэль не удалось атомарно завершить: duel_id=%s", duel_id)
            await message.answer("Результат дуэли уже обработан. При необходимости обратитесь в /paysupport.")
            return
    except Exception:
        logger.exception("Ошибка выполнения дуэли: duel_id=%s", duel_id)
        refunded = await db.refund_failed_duel(duel_id)
        text = (
            "⚠️ Дуэль не удалось провести. Обе ставки возвращены на внутренний баланс."
            if refunded
            else "⚠️ Дуэль не завершилась автоматически. Обратитесь в /paysupport."
        )
        await _safe_send(bot, creator_id, text)
        await _safe_send(bot, partner_id, text)
        return

    if winner_id is None:
        text = (
            f"🤝 <b>Ничья!</b>\n{result_text}\n\n"
            f"Ставка <b>{bet} ⭐</b> возвращена на баланс профиля."
        )
        await _safe_send(bot, creator_id, text)
        await _safe_send(bot, partner_id, text)
        return

    loser_id = partner_id if winner_id == creator_id else creator_id
    await _safe_send(
        bot,
        winner_id,
        f"🏆 <b>Вы победили!</b>\n{result_text}\n\n"
        f"На баланс начислено <b>+{credited} ⭐</b>.",
    )
    await _safe_send(bot, loser_id, f"💔 <b>Вы проиграли.</b>\n{result_text}")

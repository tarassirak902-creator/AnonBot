from __future__ import annotations

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice

from .shared import db, router


@router.callback_query(F.data.startswith("pay_duel_accept_"))
async def accept_duel_invoice(callback: CallbackQuery) -> None:
    try:
        duel_id = int((callback.data or "").rsplit("_", 1)[1])
    except (TypeError, ValueError):
        await callback.answer("Данные дуэли повреждены.", show_alert=True)
        return

    duel = await db.get_game_duel(duel_id)
    if not duel or duel[4] != "waiting":
        await callback.answer("Дуэль уже недоступна.", show_alert=True)
        return
    if int(duel[2]) != callback.from_user.id:
        await callback.answer("Этот вызов предназначен другому пользователю.", show_alert=True)
        return

    bet = int(duel[3])
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"⭐ Оплатить {bet} ⭐ для дуэли", pay=True)
    ]])
    await callback.message.answer_invoice(
        title="Принятие дуэли",
        description=f"Принятие дуэли со ставкой {bet} ⭐.",
        payload=f"duel_accept_{duel_id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"Дуэль ({bet} ⭐)", amount=bet)],
        start_parameter="duel_accept",
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("decline_duel_"))
async def decline_duel(callback: CallbackQuery) -> None:
    try:
        duel_id = int((callback.data or "").rsplit("_", 1)[1])
    except (TypeError, ValueError):
        await callback.answer("Данные дуэли повреждены.", show_alert=True)
        return

    duel = await db.get_game_duel(duel_id)
    if not duel or duel[4] != "waiting":
        await callback.answer("Дуэль уже недоступна.", show_alert=True)
        return
    if int(duel[2]) != callback.from_user.id:
        await callback.answer("Этот вызов предназначен другому пользователю.", show_alert=True)
        return

    creator_id = int(duel[1])
    await db.update_game_duel_status(duel_id, "declined")
    try:
        await callback.bot.send_message(creator_id, "❌ Собеседник отклонил вызов на дуэль.")
    except Exception as exc:
        await db.log_action(
            callback.from_user.id,
            "duel_decline_notify_error",
            f"creator_id={creator_id}; error={exc}",
        )

    await callback.answer("Дуэль отклонена.")
    try:
        await callback.message.delete()
    except Exception:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

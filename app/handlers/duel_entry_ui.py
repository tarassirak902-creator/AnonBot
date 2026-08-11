from __future__ import annotations

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.core.games import GAME_NAMES

from .shared import (
    ADMIN_IDS,
    GameDuelBet,
    db,
    duel_games_menu_kb,
    main_menu,
    router,
    safe_delete_message,
)


def _duel_bet_prompt(game_title: str) -> str:
    return (
        f"⚔️ <b>{game_title} с собеседником</b>\n"
        "───────────────\n\n"
        "Каждый игрок оплачивает свою ставку. Победитель получает <b>90% общего банка</b>.\n"
        "При ничьей обе ставки возвращаются на внутренний баланс.\n\n"
        "Введите сумму ставки для дуэли в Звёздах:"
    )


def _duel_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="↩️ Назад к выбору дуэлей",
                callback_data="duel_games_back",
            )
        ]]
    )


@router.callback_query(F.data.startswith("game_duel_"))
async def start_duel_game_entry(callback: CallbackQuery, state: FSMContext) -> None:
    if not await db.get_partner(callback.from_user.id):
        await callback.answer("Дуэли доступны только во время активного диалога.", show_alert=True)
        return

    game_type = (callback.data or "").split("_", 2)[2]
    game_title = GAME_NAMES.get(game_type, "Дуэль")
    await callback.answer()
    await safe_delete_message(callback.message)
    prompt = await callback.message.answer(
        _duel_bet_prompt(game_title),
        parse_mode="HTML",
        reply_markup=_duel_back_keyboard(),
    )
    await state.update_data(game_type=game_type, prompt_message_id=prompt.message_id)
    await state.set_state(GameDuelBet.waiting_for_bet)


@router.callback_query(F.data.startswith("duel_invoice_back:"))
async def duel_invoice_back_entry(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = callback.from_user.id
    partner_id = await db.get_partner(user_id)
    if not partner_id:
        await state.clear()
        await callback.answer("Диалог уже завершён.", show_alert=True)
        await safe_delete_message(callback.message)
        await callback.message.answer(
            "👻 Диалог уже завершён.",
            reply_markup=main_menu(user_id in ADMIN_IDS),
        )
        return

    game_type = (callback.data or "").split(":", 1)[1]
    game_title = GAME_NAMES.get(game_type, "Дуэль")
    await callback.answer()
    await safe_delete_message(callback.message)
    prompt = await callback.message.answer(
        _duel_bet_prompt(game_title),
        parse_mode="HTML",
        reply_markup=_duel_back_keyboard(),
    )
    await state.update_data(game_type=game_type, prompt_message_id=prompt.message_id)
    await state.set_state(GameDuelBet.waiting_for_bet)

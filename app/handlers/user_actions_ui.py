from __future__ import annotations

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.core.ui_copy import screen
from app.core.ui_labels import ButtonText

from .shared import (
    db,
    router,
    complaint_reasons,
    duel_games_menu_kb,
    hide_reply_keyboard,
    solo_games_menu_kb,
)


@router.message(F.text.in_({"Мини игры", "🎮 Мини-игры"}))
async def games_entry_ui(message: Message, state: FSMContext) -> None:
    await state.clear()
    await hide_reply_keyboard(message)
    await message.answer(
        screen(
            "🎮 Мини-игры",
            intro="Выберите одиночную игру против CASPER.",
            footer="Ставки и награды указаны внутри выбранной игры.",
        ),
        parse_mode="HTML",
        reply_markup=solo_games_menu_kb(),
    )


@router.message(F.text == "⚔️ Играть с собеседником")
async def duel_games_entry_ui(message: Message, state: FSMContext) -> None:
    await state.clear()
    if not await db.get_partner(message.from_user.id):
        await message.answer(
            screen(
                "⚔️ Дуэли",
                intro="Дуэли доступны только во время активного диалога.",
                footer="Сначала найдите собеседника.",
            ),
            parse_mode="HTML",
        )
        return
    await message.answer(
        screen(
            "⚔️ Дуэли",
            intro="Выберите режим игры с собеседником.",
        ),
        parse_mode="HTML",
        reply_markup=duel_games_menu_kb(),
    )


@router.message(F.text == "⚠️ Пожаловаться")
async def complaint_entry_ui(message: Message) -> None:
    if not await db.get_partner(message.from_user.id):
        await message.answer(
            screen(
                "⚠️ Жалоба",
                intro="Жалобу можно отправить только во время активного диалога.",
            ),
            parse_mode="HTML",
        )
        return
    await message.answer(
        screen(
            "⚠️ Жалоба",
            intro="Выберите причину. Жалоба будет передана модераторам.",
            footer="Используйте жалобы только при нарушении правил.",
        ),
        parse_mode="HTML",
        reply_markup=complaint_reasons(),
    )


@router.message(F.text == "🎁 Подарить подарок")
async def gifts_entry_ui(message: Message) -> None:
    user_id = message.from_user.id
    if not await db.get_partner(user_id):
        await message.answer(
            screen(
                "🎁 Подарки",
                intro="Подарки можно отправлять только во время активного диалога.",
            ),
            parse_mode="HTML",
        )
        return

    gifts = await db.get_all_gifts()
    if not gifts:
        await message.answer(
            screen("🎁 Подарки", intro="Сейчас нет доступных подарков."),
            parse_mode="HTML",
        )
        return

    is_vip = await db.is_user_vip(user_id)
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for gift_id, name, emoji, price in gifts:
        actual_price = int(price * 0.7) if is_vip else price
        discount = " · VIP −30%" if is_vip else ""
        row.append(
            InlineKeyboardButton(
                text=f"{emoji} {name} · {actual_price} ⭐{discount}",
                callback_data=f"buy_gift_{gift_id}",
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([
        InlineKeyboardButton(text=ButtonText.CLOSE, callback_data="close_gifts_menu")
    ])

    await message.answer(
        screen(
            "🎁 Подарки",
            intro="Выберите подарок для собеседника.",
            footer="Стоимость будет списана с баланса после подтверждения.",
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )

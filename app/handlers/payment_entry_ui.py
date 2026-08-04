from __future__ import annotations

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice

from app.core.action_ui import payment_description, withdraw_screen

from .shared import UserWithdraw, db, pending_invoice_message_ids, router, safe_delete_message


@router.callback_query(F.data == "buy_vip_sub")
async def buy_vip_entry(callback: CallbackQuery) -> None:
    await callback.answer()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👑 Оплатить 100 ⭐", pay=True)],
        [InlineKeyboardButton(text="⬅️ Назад в профиль", callback_data="profile_back")],
    ])
    await safe_delete_message(callback.message)
    invoice = await callback.message.answer_invoice(
        title="VIP на 30 дней",
        description=payment_description(
            "VIP-подписка CASPER",
            "Скидка 30% на подарки и дополнительные возможности профиля",
            "Срок действия — 30 дней",
        ),
        payload="vip_subscription_100",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="VIP на 30 дней", amount=100)],
        start_parameter="vip_sub",
        reply_markup=keyboard,
    )
    pending_invoice_message_ids[callback.from_user.id] = invoice.message_id


@router.callback_query(F.data == "profile_withdraw")
async def profile_withdraw_entry(callback: CallbackQuery, state: FSMContext) -> None:
    balance = await db.get_user_balance(callback.from_user.id)
    if balance <= 0:
        await callback.answer("На балансе пока нет звёзд для вывода.", show_alert=True)
        return

    await callback.answer()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад в профиль", callback_data="profile_back")]
    ])
    await safe_delete_message(callback.message)
    await callback.message.answer(
        withdraw_screen(balance),
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    await state.set_state(UserWithdraw.waiting_for_amount)

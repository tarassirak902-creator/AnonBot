from __future__ import annotations

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from .callbacks_profile import buy_vip_sub_handler, profile_invited_handler, profile_withdraw_start
from .shared import router


@router.callback_query(F.data == "profile_social_invites")
async def profile_social_invites(callback: CallbackQuery) -> None:
    await profile_invited_handler(callback)


@router.callback_query(F.data == "profile_premium_vip")
async def profile_premium_vip(callback: CallbackQuery) -> None:
    await buy_vip_sub_handler(callback)


# Context aliases are registered separately from legacy callbacks so new hubs can
# migrate without breaking old deep links. The legacy screens themselves are
# being retired progressively as part of Platform 5.0.

from __future__ import annotations

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.core.ui_renderer import render_message
from app.database.platform_growth_repository import record_product_event
from app.database.platform_personal_goals_repository import record_personal_goal_event
from app.database.platform_referral_repository import get_referral_summary
from .shared import router


def _referral_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Моя ссылка", callback_data="referral_stats_growth")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="platform_referrals")],
        [InlineKeyboardButton(text="⬅️ Центр роста", callback_data="growth_center")],
    ])


@router.callback_query(F.data == "platform_referrals")
async def platform_referrals(callback: CallbackQuery) -> None:
    await callback.answer()
    await record_product_event(callback.from_user.id, "referral_center_open")
    await record_personal_goal_event(callback.from_user.id, "referral_open")
    summary = await get_referral_summary(callback.from_user.id)
    text = (
        "<b>👥 Приглашения</b>\n\n"
        f"Зарегистрировано: <b>{summary.registered}</b>\n"
        f"Активировано: <b>{summary.activated}</b>\n"
        f"Награды получены: <b>{summary.rewarded}</b>\n"
        f"Ожидают начисления: <b>{summary.pending_rewards}</b>\n\n"
        "Друг становится активным после 5 завершённых диалогов. "
        "Каждое приглашение и награда учитываются только один раз."
    )
    await render_message(callback.message, text, reply_markup=_referral_keyboard())

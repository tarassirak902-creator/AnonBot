from __future__ import annotations

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app import database as db
from .shared import router
from .profile_view import build_profile_screen


@router.callback_query(F.data == "profile_daily_reward")
async def profile_daily_reward(callback: CallbackQuery, state: FSMContext) -> None:
    result = await db.claim_daily_reward(callback.from_user.id)
    if not result["claimed"]:
        await callback.answer(
            f"Бонус уже получен. Серия: {result['streak']} 🔥",
            show_alert=True,
        )
        return

    await callback.answer(
        f"+{result['reward']} XP · серия {result['streak']} 🔥",
        show_alert=True,
    )
    profile = await build_profile_screen(callback.from_user.id)
    if profile is not None:
        text, keyboard = profile
        try:
            await callback.message.edit_caption(
                caption=text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        except Exception:
            try:
                await callback.message.edit_text(
                    text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
            except Exception:
                pass


def rating_keyboard(partner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ Отлично", callback_data=f"rate_partner:{partner_id}:1"),
            InlineKeyboardButton(text="🙂 Нормально", callback_data=f"rate_partner:{partner_id}:0"),
        ],
        [InlineKeyboardButton(text="👎 Плохо", callback_data=f"rate_partner:{partner_id}:-1")],
    ])


@router.callback_query(F.data.startswith("rate_partner:"))
async def rate_partner(callback: CallbackQuery) -> None:
    try:
        _, partner_raw, score_raw = callback.data.split(":", 2)
        partner_id = int(partner_raw)
        score = int(score_raw)
    except (TypeError, ValueError):
        await callback.answer("Оценка устарела", show_alert=True)
        return

    if partner_id == callback.from_user.id:
        await callback.answer("Нельзя оценить себя", show_alert=True)
        return

    await db.rate_user(callback.from_user.id, partner_id, score)
    await db.add_xp(callback.from_user.id, 5)
    await callback.answer("Спасибо за оценку! +5 XP", show_alert=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

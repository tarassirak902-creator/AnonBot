from __future__ import annotations

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

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


@router.callback_query(F.data.startswith("rate_partner:"))
async def retired_legacy_rating(callback: CallbackQuery) -> None:
    """Close old partner-id rating buttons without trusting their embedded user id.

    Current ratings use single-use ``dialog_rate:*`` tokens from
    ``platform_automation_ui``. Old Telegram messages can live for months, so the
    route remains as a compatibility tombstone instead of executing the historical
    non-idempotent rating/XP flow.
    """
    await callback.answer(
        "Эта кнопка оценки устарела. Новые оценки появляются после завершения диалога.",
        show_alert=True,
    )
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

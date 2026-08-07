from __future__ import annotations

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.core.ui_renderer import render_callback, render_message
from app.database.platform_personal_goals_repository import (
    GOAL_REWARD_STARS,
    GOAL_REWARD_XP,
    claim_personal_goal_reward,
    get_personal_goal_metrics,
    get_personal_goal_profile,
)
from app.database.platform_progress_repository import grant_xp_once
from .shared import ADMIN_IDS, db, router


def _goal_keyboard(can_claim: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if can_claim:
        rows.append([InlineKeyboardButton(text=f"🎁 Забрать {GOAL_REWARD_STARS} ⭐", callback_data="personal_goal_claim")])
    rows += [
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="personal_goals")],
        [InlineKeyboardButton(text="⬅️ Центр роста", callback_data="growth_center")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _goal_screen(user_id: int) -> tuple[str, bool]:
    profile = await get_personal_goal_profile(user_id)
    lines = []
    for goal in profile.goals:
        marker = "✅" if goal.completed else "▫️"
        lines.append(f"{marker} {goal.title}")
    can_claim = profile.completed >= profile.target and not profile.reward_claimed
    if profile.reward_claimed:
        status = "✅ Награда получена"
    elif can_claim:
        status = "🎁 Награда доступна"
    else:
        status = f"⏳ Выполнено {profile.completed}/{profile.target}"
    text = (
        "<b>🧭 План на сегодня</b>\n\n"
        + "\n".join(lines)
        + "\n\n"
        + f"Награда: <b>{GOAL_REWARD_STARS} ⭐ + {GOAL_REWARD_XP} XP</b>\n"
        + f"Статус: <b>{status}</b>\n\n"
        + "Цели меняются ежедневно и засчитываются только по фактическим действиям."
    )
    return text, can_claim


@router.callback_query(F.data == "personal_goals")
async def personal_goals(callback: CallbackQuery) -> None:
    text, can_claim = await _goal_screen(callback.from_user.id)
    await render_callback(callback, text, reply_markup=_goal_keyboard(can_claim))


@router.callback_query(F.data == "personal_goal_claim")
async def personal_goal_claim(callback: CallbackQuery) -> None:
    claimed = await claim_personal_goal_reward(callback.from_user.id)
    if not claimed:
        await callback.answer("Награда недоступна или уже получена", show_alert=True)
    else:
        try:
            await db.add_user_balance(callback.from_user.id, GOAL_REWARD_STARS)
            await grant_xp_once(
                callback.from_user.id,
                f"personal_goal:{callback.from_user.id}:{__import__('datetime').date.today().isoformat()}",
                GOAL_REWARD_XP,
                weekly_increment=1,
            )
        except Exception:
            await callback.answer("Награда отмечена, баланс будет проверен", show_alert=True)
        else:
            await callback.answer(f"Получено {GOAL_REWARD_STARS} ⭐ и {GOAL_REWARD_XP} XP")
    text, can_claim = await _goal_screen(callback.from_user.id)
    if callback.message is not None:
        await render_message(callback.message, text, reply_markup=_goal_keyboard(can_claim))


@router.callback_query(F.data == "admin_personal_goals")
async def admin_personal_goals(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    metrics = await get_personal_goal_metrics()
    text = (
        "<b>🧭 Personal Goals</b>\n\n"
        f"Участников сегодня: <b>{metrics.participants_today}</b>\n"
        f"Выполнили 3/3: <b>{metrics.completed_today}</b>\n"
        f"Награды получены: <b>{metrics.rewards_today}</b>\n"
        f"Конверсия выполнения: <b>{metrics.completion_rate}%</b>\n\n"
        "Воронка строится только по техническим событиям без текста сообщений."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_personal_goals")],
        [InlineKeyboardButton(text="⬅️ Рост", callback_data="admin_growth_operations")],
    ])
    await render_callback(callback, text, reply_markup=kb, answer_text="Обновлено")

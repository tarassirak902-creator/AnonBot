from __future__ import annotations

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.core.action_flow import run_state_action
from app.core.ui_renderer import render_callback, render_message
from app.database.platform_growth_repository import record_product_event
from app.database.platform_missions_repository import (
    MISSION_STAR_REWARD,
    MISSION_XP_REWARD,
    claim_mission_reward,
    get_mission_metrics,
    get_mission_profile,
)
from app.database.platform_personal_goals_repository import record_personal_goal_event
from .shared import ADMIN_IDS, router


def _mission_keyboard(can_claim: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if can_claim:
        rows.append([InlineKeyboardButton(text=f"🎁 Забрать {MISSION_STAR_REWARD} ⭐", callback_data="mission_reward_claim")])
    rows += [
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="season_missions")],
        [InlineKeyboardButton(text="⬅️ Центр роста", callback_data="growth_center")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _mission_screen(user_id: int) -> tuple[str, bool]:
    profile = await get_mission_profile(user_id)
    can_claim = profile.completed and not profile.reward_claimed
    status = "✅ Получена" if profile.reward_claimed else ("🎁 Доступна" if can_claim else "⏳ В процессе")
    text = (
        "<b>🎯 Сезонные задания</b>\n\n"
        f"Полезные действия: <b>{profile.progress}/{profile.target}</b>\n"
        f"Награда: <b>{MISSION_STAR_REWARD} ⭐ + {MISSION_XP_REWARD} XP</b>\n"
        f"Статус: <b>{status}</b>\n\n"
        "В прогресс засчитываются только уникальные действия. Повторное нажатие одной кнопки не увеличивает результат."
    )
    return text, can_claim


@router.callback_query(F.data == "season_missions")
async def season_missions(callback: CallbackQuery) -> None:
    await record_product_event(callback.from_user.id, "season_missions_open")
    await record_personal_goal_event(callback.from_user.id, "missions_open")
    text, can_claim = await _mission_screen(callback.from_user.id)
    await render_callback(callback, text, reply_markup=_mission_keyboard(can_claim))


@router.callback_query(F.data == "mission_reward_claim")
async def mission_reward_claim(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id

    async def render() -> None:
        text, can_claim = await _mission_screen(user_id)
        if callback.message is not None:
            await render_message(callback.message, text, reply_markup=_mission_keyboard(can_claim))

    await run_state_action(
        callback,
        action=lambda: claim_mission_reward(user_id),
        render=render,
        success_text=f"Получено {MISSION_STAR_REWARD} ⭐ и {MISSION_XP_REWARD} XP",
        noop_text="Награда недоступна или уже получена",
        error_text="Не удалось начислить награду. Попробуйте ещё раз",
        on_success=lambda: record_product_event(user_id, "season_mission_reward"),
    )


@router.callback_query(F.data == "admin_mission_metrics")
async def admin_mission_metrics(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    metrics = await get_mission_metrics()
    text = (
        "<b>🎯 Missions & Rewards</b>\n\n"
        f"Участников: <b>{metrics.participants}</b>\n"
        f"Завершили сезонную цель: <b>{metrics.completed}</b>\n"
        f"Награды получены: <b>{metrics.rewards_claimed}</b>\n"
        f"Уникальных событий за 7 дней: <b>{metrics.events_7d}</b>\n\n"
        "Метрики строятся по идентификаторам событий без содержимого сообщений."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_mission_metrics")],
        [InlineKeyboardButton(text="⬅️ Рост", callback_data="admin_growth_operations")],
    ])
    await render_callback(callback, text, reply_markup=kb, answer_text="Обновлено")

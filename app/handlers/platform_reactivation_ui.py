from __future__ import annotations

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.core.action_flow import run_state_action
from app.core.ui_renderer import render_callback, render_message
from app.database.platform_reactivation_repository import (
    COMEBACK_REWARD_STARS,
    COMEBACK_REWARD_XP,
    claim_reactivation_reward,
    get_reactivation_metrics,
    get_reactivation_profile,
    record_reactivation_visit,
)
from .shared import ADMIN_IDS, router


def _reactivation_keyboard(can_claim: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if can_claim:
        rows.append([
            InlineKeyboardButton(
                text=f"🎁 Вернуться +{COMEBACK_REWARD_STARS} ⭐",
                callback_data="reactivation_claim",
            )
        ])
    rows += [
        [InlineKeyboardButton(text="🧭 План", callback_data="personal_goals")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="reactivation_center")],
        [InlineKeyboardButton(text="⬅️ Центр роста", callback_data="growth_center")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _reactivation_screen(user_id: int, *, record_visit: bool) -> tuple[str, bool]:
    profile = (
        await record_reactivation_visit(user_id)
        if record_visit
        else await get_reactivation_profile(user_id)
    )
    if profile.reward_claimed_this_week:
        status = "✅ Бонус этой недели получен"
    elif profile.reward_available:
        status = "🎁 Comeback-бонус доступен"
    else:
        status = "🌿 Активность стабильна"
    gap_line = (
        f"⏳ Последний возврат после паузы: <b>{profile.days_away} дн.</b>\n"
        if profile.days_away > 0
        else "⏳ Сегодня без длинной паузы\n"
    )
    text = (
        "<b>🌙 Возвращение</b>\n\n"
        + gap_line
        + f"🔁 Возвращений: <b>{profile.comeback_count}</b>\n"
        + f"🏆 Самая длинная пауза: <b>{profile.best_gap_days} дн.</b>\n"
        + f"Статус: <b>{status}</b>\n\n"
        + f"За реальный возврат после паузы можно получить <b>{COMEBACK_REWARD_STARS} ⭐ + {COMEBACK_REWARD_XP} XP</b> один раз в неделю."
    )
    return text, profile.reward_available


@router.callback_query(F.data == "reactivation_center")
async def reactivation_center(callback: CallbackQuery) -> None:
    text, can_claim = await _reactivation_screen(callback.from_user.id, record_visit=True)
    await render_callback(callback, text, reply_markup=_reactivation_keyboard(can_claim))


@router.callback_query(F.data == "reactivation_claim")
async def reactivation_claim(callback: CallbackQuery) -> None:
    async def render() -> None:
        text, can_claim = await _reactivation_screen(callback.from_user.id, record_visit=False)
        if callback.message is not None:
            await render_message(callback.message, text, reply_markup=_reactivation_keyboard(can_claim))

    await run_state_action(
        callback,
        action=lambda: claim_reactivation_reward(callback.from_user.id),
        render=render,
        success_text=f"Получено {COMEBACK_REWARD_STARS} ⭐ и {COMEBACK_REWARD_XP} XP",
        noop_text="Бонус недоступен или уже получен",
        error_text="Не удалось начислить comeback-бонус. Попробуйте ещё раз",
    )


@router.callback_query(F.data == "admin_reactivation_metrics")
async def admin_reactivation_metrics(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    metrics = await get_reactivation_metrics()
    text = (
        "<b>🌙 Reactivation</b>\n\n"
        f"Возвратов за 7 дней: <b>{metrics.returns_7d}</b>\n"
        f"Уникальных вернувшихся: <b>{metrics.unique_returners_7d}</b>\n"
        f"Получено comeback-бонусов: <b>{metrics.rewards_7d}</b>\n"
        f"Средняя пауза: <b>{metrics.avg_gap_days} дн.</b>\n"
        f"Максимальная пауза: <b>{metrics.max_gap_days} дн.</b>\n\n"
        "Система хранит только даты возвратов и длительность паузы."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_reactivation_metrics")],
        [InlineKeyboardButton(text="⬅️ Рост", callback_data="admin_growth_operations")],
    ])
    await render_callback(callback, text, reply_markup=kb, answer_text="Обновлено")

from __future__ import annotations

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.core.action_flow import run_state_action
from app.core.navigation import screen_back_button, screen_refresh_button
from app.core.ui_renderer import render_message
from app.database.platform_growth_repository import claim_daily_activity, get_daily_activity, get_growth_metrics, record_product_event
from app.database.platform_personal_goals_repository import record_personal_goal_event
from .shared import ADMIN_IDS, router


def _growth_keyboard(claimed: bool) -> InlineKeyboardMarkup:
    rows = []
    if not claimed:
        rows.append([InlineKeyboardButton(text="🎁 Забрать бонус", callback_data="growth_daily_claim")])
    rows += [
        [
            InlineKeyboardButton(text="🧭 План", callback_data="personal_goals"),
            InlineKeyboardButton(text="🌙 Возврат", callback_data="reactivation_center"),
        ],
        [
            InlineKeyboardButton(text="🏆 Прогресс", callback_data="progress_center"),
            InlineKeyboardButton(text="🎯 Задания", callback_data="season_missions"),
        ],
        [
            InlineKeyboardButton(text="👥 Приглашения", callback_data="platform_referrals"),
            InlineKeyboardButton(text="🏪 Магазин", callback_data="platform_shop"),
        ],
        [screen_refresh_button("growth")],
        [screen_back_button("growth")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _growth_text(user_id: int) -> tuple[str, bool]:
    activity = await get_daily_activity(user_id)
    status = "✅ Получен" if activity.claimed_today else "🎁 Доступен"
    return (
        "<b>🚀 Центр роста</b>\n\n"
        f"🔥 Текущая серия: <b>{activity.streak} дн.</b>\n"
        f"🏆 Лучшая серия: <b>{activity.best_streak} дн.</b>\n"
        f"Сегодняшний бонус: <b>{status}</b>\n"
        f"Следующая награда: <b>{activity.next_reward} ⭐</b>\n\n"
        "Выполняй персональный план, развивай уровень, возвращайся после пауз и закрывай сезонные задания."
    ), activity.claimed_today


@router.callback_query(F.data == "growth_center")
async def growth_center(callback: CallbackQuery) -> None:
    await callback.answer()
    await record_product_event(callback.from_user.id, "growth_center_open")
    await record_personal_goal_event(callback.from_user.id, "growth_open")
    text, claimed = await _growth_text(callback.from_user.id)
    await render_message(callback.message, text, reply_markup=_growth_keyboard(claimed))


@router.callback_query(F.data == "growth_daily_claim")
async def growth_daily_claim(callback: CallbackQuery) -> None:
    result = {"reward": 0}

    async def action() -> bool:
        claimed, _activity, reward = await claim_daily_activity(callback.from_user.id)
        result["reward"] = reward
        return claimed

    async def render() -> None:
        text, claimed = await _growth_text(callback.from_user.id)
        if callback.message is not None:
            await render_message(callback.message, text, reply_markup=_growth_keyboard(claimed))

    await run_state_action(
        callback,
        action=action,
        render=render,
        success_text=lambda: f"Получено {result['reward']} ⭐",
        noop_text="Бонус уже получен сегодня",
        error_text="Не удалось начислить бонус. Попробуйте ещё раз",
        on_success=lambda: record_personal_goal_event(callback.from_user.id, "daily_claim"),
    )


def _admin_growth_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧠 Качество", callback_data="admin_match_quality")],
        [
            InlineKeyboardButton(text="🧭 План", callback_data="admin_personal_goals"),
            InlineKeyboardButton(text="🌙 Возврат", callback_data="admin_reactivation_metrics"),
        ],
        [
            InlineKeyboardButton(text="🏆 Прогресс", callback_data="admin_progress_metrics"),
            InlineKeyboardButton(text="🎯 Задания", callback_data="admin_mission_metrics"),
        ],
        [
            InlineKeyboardButton(text="📈 Воронка", callback_data="admin_product_funnel"),
            InlineKeyboardButton(text="💼 Бизнес", callback_data="admin_business_from_growth"),
        ],
        [
            InlineKeyboardButton(text="📡 Операции", callback_data="admin_ops_from_growth"),
            InlineKeyboardButton(text="🩺 Система", callback_data="admin_platform_health_from_growth"),
        ],
        [screen_refresh_button("admin_growth")],
        [screen_back_button("admin_growth")],
    ])


@router.callback_query(F.data == "admin_growth_operations")
async def admin_growth_operations(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    metrics = await get_growth_metrics()
    text = (
        "<b>🚀 Growth & Operations</b>\n\n"
        f"DAU: <b>{metrics.dau}</b>\n"
        f"WAU: <b>{metrics.wau}</b>\n"
        f"MAU: <b>{metrics.mau}</b>\n\n"
        f"🎁 Бонусов за 24 ч.: <b>{metrics.daily_claims}</b>\n"
        f"🔥 Активных серий: <b>{metrics.active_streaks}</b>\n"
        f"📊 Событий за 24 ч.: <b>{metrics.product_events_24h}</b>\n\n"
        "Метрики формируются без хранения содержимого сообщений."
    )
    await callback.answer("Обновлено")
    await render_message(callback.message, text, reply_markup=_admin_growth_keyboard())

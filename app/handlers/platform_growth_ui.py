from __future__ import annotations

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.core.ui_renderer import render_message
from app.database.platform_growth_repository import claim_daily_activity, get_daily_activity, get_growth_metrics, record_product_event
from app.database.platform_personal_goals_repository import record_personal_goal_event
from .shared import ADMIN_IDS, db, router


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
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="growth_center")],
        [InlineKeyboardButton(text="⬅️ Мой день", callback_data="commercial_daily_hub")],
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
    claimed, activity, reward = await claim_daily_activity(callback.from_user.id)
    if not claimed:
        await callback.answer("Бонус уже получен сегодня", show_alert=True)
    else:
        try:
            await db.add_user_balance(callback.from_user.id, reward)
        except Exception:
            await callback.answer("Награда записана, баланс обновится после проверки", show_alert=True)
        else:
            await record_personal_goal_event(callback.from_user.id, "daily_claim")
            await callback.answer(f"Получено {reward} ⭐")
    text, _ = await _growth_text(callback.from_user.id)
    await render_message(callback.message, text, reply_markup=_growth_keyboard(activity.claimed_today))


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
            InlineKeyboardButton(text="📈 Аналитика", callback_data="admin_retention_from_growth"),
            InlineKeyboardButton(text="💼 Бизнес", callback_data="admin_business_from_growth"),
        ],
        [
            InlineKeyboardButton(text="📡 Операции", callback_data="admin_ops_from_growth"),
            InlineKeyboardButton(text="🩺 Система", callback_data="admin_platform_health_from_growth"),
        ],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_growth_operations")],
        [InlineKeyboardButton(text="⬅️ Управление", callback_data="admin_commercial_hub")],
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

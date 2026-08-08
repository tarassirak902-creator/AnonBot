from __future__ import annotations

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.core.ui_renderer import render_callback, render_message
from app.database.platform_growth_repository import record_product_event
from app.database.platform_progress_repository import (
    WEEKLY_REWARD,
    claim_weekly_reward,
    get_progress_metrics,
    get_progress_profile,
)
from .shared import ADMIN_IDS, router


def _progress_keyboard(can_claim: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if can_claim:
        rows.append([InlineKeyboardButton(text=f"🎁 Забрать {WEEKLY_REWARD} ⭐", callback_data="progress_weekly_claim")])
    rows += [
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="progress_center")],
        [InlineKeyboardButton(text="⬅️ Центр роста", callback_data="growth_center")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _progress_screen(user_id: int) -> tuple[str, bool]:
    profile = await get_progress_profile(user_id)
    can_claim = profile.weekly_progress >= profile.weekly_target and not profile.weekly_reward_claimed
    reward_status = "✅ Получена" if profile.weekly_reward_claimed else ("🎁 Доступна" if can_claim else "⏳ В процессе")
    text = (
        "<b>🏆 Прогресс</b>\n\n"
        f"Уровень: <b>{profile.level} · {profile.level_name}</b>\n"
        f"Опыт: <b>{profile.xp} XP</b>\n"
        f"До следующего уровня: <b>{profile.current_level_xp}/{profile.next_level_xp} XP</b>\n\n"
        f"📅 Недельная цель: <b>{profile.weekly_progress}/{profile.weekly_target}</b>\n"
        f"Награда: <b>{reward_status}</b>\n\n"
        "Прогресс растёт за полезные действия и учитывается только один раз для каждого события."
    )
    return text, can_claim


@router.callback_query(F.data == "progress_center")
async def progress_center(callback: CallbackQuery) -> None:
    await record_product_event(callback.from_user.id, "progress_center_open")
    text, can_claim = await _progress_screen(callback.from_user.id)
    await render_callback(callback, text, reply_markup=_progress_keyboard(can_claim))


@router.callback_query(F.data == "progress_weekly_claim")
async def progress_weekly_claim(callback: CallbackQuery) -> None:
    try:
        claimed = await claim_weekly_reward(callback.from_user.id)
    except Exception:
        answer_text = "Не удалось начислить награду. Попробуйте ещё раз"
        show_alert = True
    else:
        if claimed:
            await record_product_event(callback.from_user.id, "weekly_reward_claim")
            answer_text = f"Получено {WEEKLY_REWARD} ⭐"
            show_alert = False
        else:
            answer_text = "Награда недоступна или уже получена"
            show_alert = True
    await callback.answer(answer_text, show_alert=show_alert)
    text, can_claim = await _progress_screen(callback.from_user.id)
    if callback.message is not None:
        await render_message(callback.message, text, reply_markup=_progress_keyboard(can_claim))


@router.callback_query(F.data == "admin_progress_metrics")
async def admin_progress_metrics(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    metrics = await get_progress_metrics()
    text = (
        "<b>🏆 Progress & Retention</b>\n\n"
        f"Пользователей с прогрессом: <b>{metrics.tracked_users}</b>\n"
        f"Уровень 5+: <b>{metrics.level_5_plus}</b>\n"
        f"Недельная цель выполнена: <b>{metrics.weekly_completed}</b>\n"
        f"Недельных наград получено: <b>{metrics.weekly_rewards_claimed}</b>\n"
        f"XP выдано за 7 дней: <b>{metrics.xp_issued_7d}</b>\n\n"
        "Метрики не содержат тексты сообщений пользователей."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_progress_metrics")],
        [InlineKeyboardButton(text="⬅️ Рост", callback_data="admin_growth_operations")],
    ])
    await render_callback(callback, text, reply_markup=kb, answer_text="Обновлено")

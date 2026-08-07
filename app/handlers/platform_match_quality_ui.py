from __future__ import annotations

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.database.platform_match_quality_repository import get_match_quality_metrics
from .shared import ADMIN_IDS, router


def _keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_match_quality")],
        [InlineKeyboardButton(text="⬅️ Рост", callback_data="admin_growth_operations")],
    ])


@router.callback_query(F.data == "admin_match_quality")
async def admin_match_quality(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    metrics = await get_match_quality_metrics()
    text = (
        "<b>🧠 Качество матчей</b>\n\n"
        f"👥 Пользователей с оценками: <b>{metrics.rated_users}</b>\n"
        f"⭐ Всего оценок: <b>{metrics.ratings}</b>\n\n"
        f"👍 Положительных: <b>{metrics.positive}</b>\n"
        f"🙂 Нейтральных: <b>{metrics.neutral}</b>\n"
        f"👎 Отрицательных: <b>{metrics.negative}</b>\n\n"
        f"⚠️ Устойчиво низкое качество: <b>{metrics.low_quality_users}</b>\n\n"
        "Подбор использует только агрегированные оценки диалогов. Текст сообщений не анализируется."
    )
    await callback.answer("Обновлено")
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=_keyboard())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=_keyboard())

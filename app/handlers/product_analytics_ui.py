from __future__ import annotations

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.database.product_analytics_repository import get_funnel_metrics
from .shared import ADMIN_IDS, router


def _pct(value: int, total: int) -> str:
    return "—" if total <= 0 else f"{round(value * 100 / total)}%"


@router.callback_query(F.data == "admin_product_funnel")
async def admin_product_funnel(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    data = await get_funnel_metrics(7)
    text = (
        "<b>📊 Продуктовая воронка · 7 дней</b>\n\n"
        f"👋 /start: <b>{data.starts}</b>\n"
        f"🔎 Поиск: <b>{data.searchers}</b> · {_pct(data.searchers, data.starts)} от start\n"
        f"🤝 Match: <b>{data.matched}</b> · {_pct(data.matched, data.searchers)} от search\n"
        f"✅ Диалог ≥60 сек: <b>{data.completed}</b> · {_pct(data.completed, data.matched)} от match\n"
        f"🔁 Повторный поиск: <b>{data.repeat_searchers}</b> · {_pct(data.repeat_searchers, data.searchers)}\n\n"
        f"D1: <b>{data.d1_returned}/{data.d1_eligible}</b> · {_pct(data.d1_returned, data.d1_eligible)}\n"
        f"D7: <b>{data.d7_returned}/{data.d7_eligible}</b> · {_pct(data.d7_returned, data.d7_eligible)}\n\n"
        "<i>Метрики начинают накапливаться после включения этой аналитики. Содержимое сообщений не хранится.</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_product_funnel")],
        [InlineKeyboardButton(text="⬅️ Growth", callback_data="admin_growth_operations")],
    ])
    await callback.answer("Обновлено")
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

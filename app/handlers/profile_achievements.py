from __future__ import annotations

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app import database as db
from app.handlers.shared import router, safe_delete_message
from app.services.profile_insights import build_achievements, load_profile_insights


@router.callback_query(F.data == "profile_achievements")
async def profile_achievements_handler(callback: CallbackQuery) -> None:
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Не удалось загрузить достижения.", show_alert=True)
        return

    joined_at = user[4] if len(user) > 4 else None
    insights = await load_profile_insights(callback.from_user.id, joined_at)
    is_vip = await db.is_user_vip(callback.from_user.id)
    stars_balance = await db.get_user_balance(callback.from_user.id)
    achievements = build_achievements(insights, is_vip=is_vip, stars_balance=stars_balance)

    rows = []
    for item in achievements:
        marker = "✅" if item.unlocked else "🔒"
        rows.append(f"{marker} {item.icon} <b>{item.title}</b>\n<i>{item.description}</i>")

    text = (
        "🏆 <b>Достижения CASPER</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        + "\n\n".join(rows)
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="profile_achievements")],
        [InlineKeyboardButton(text="↩️ Назад в профиль", callback_data="profile_back")],
    ])

    await callback.answer()
    await safe_delete_message(callback.message)
    await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)

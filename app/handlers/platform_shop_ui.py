from __future__ import annotations

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.database.platform_growth_repository import acquire_action_slot, record_product_event
from app.database.platform_personal_goals_repository import record_personal_goal_event
from .shared import router


_CATEGORIES = {
    "style": ("🎨 Оформление", "Рамки, акценты профиля и визуальные элементы.", "profile_customization"),
    "premium": ("👑 Premium", "Подписка и расширенные возможности аккаунта.", "profile_vip"),
    "gifts": ("🎁 Подарки", "Подарки и знаки внимания другим пользователям.", "profile_gifts"),
    "boosts": ("⭐ Бонусы", "Полезные усиления и временные преимущества.", "profile_shop"),
    "seasonal": ("🎉 Сезонное", "Ограниченные предложения и коллекционные предметы.", "weekly_event_hub"),
}


def _shop_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎨 Оформление", callback_data="shop_category:style"),
            InlineKeyboardButton(text="👑 Premium", callback_data="shop_category:premium"),
        ],
        [
            InlineKeyboardButton(text="🎁 Подарки", callback_data="shop_category:gifts"),
            InlineKeyboardButton(text="⭐ Бонусы", callback_data="shop_category:boosts"),
        ],
        [InlineKeyboardButton(text="🎉 Сезонное", callback_data="shop_category:seasonal")],
        [InlineKeyboardButton(text="⬅️ Центр роста", callback_data="growth_center")],
    ])


@router.callback_query(F.data == "platform_shop")
async def platform_shop(callback: CallbackQuery) -> None:
    await callback.answer()
    await record_product_event(callback.from_user.id, "shop_open")
    await record_personal_goal_event(callback.from_user.id, "shop_open")
    text = (
        "<b>🏪 Магазин</b>\n\n"
        "Выберите категорию. Покупки и переходы используют единые безопасные маршруты.\n\n"
        "⭐ Баланс и доступность товара проверяются непосредственно перед оплатой."
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=_shop_keyboard())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=_shop_keyboard())


@router.callback_query(F.data.startswith("shop_category:"))
async def shop_category(callback: CallbackQuery) -> None:
    key = callback.data.partition(":")[2]
    category = _CATEGORIES.get(key)
    if not category:
        await callback.answer("Категория не найдена", show_alert=True)
        return
    allowed = await acquire_action_slot(callback.from_user.id, f"shop:{key}", 2)
    if not allowed:
        await callback.answer("Подождите пару секунд", show_alert=True)
        return
    title, description, target = category
    await record_product_event(callback.from_user.id, f"shop_category_{key}")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Открыть предложения", callback_data=target)],
        [InlineKeyboardButton(text="⬅️ Категории", callback_data="platform_shop")],
    ])
    await callback.answer()
    text = f"<b>{title}</b>\n\n{description}\n\nПеред покупкой бот повторно проверит цену, баланс и доступность."
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)

from __future__ import annotations

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.core.ui_copy import metric, screen, section
from app.services.platform_commercial import load_business_metrics, load_user_commercial_status

from .shared import ADMIN_IDS, router


def _progress_bar(progress: int) -> str:
    filled = max(0, min(10, progress // 10))
    return "█" * filled + "░" * (10 - filled)


@router.callback_query(F.data == "profile_platform_status")
async def profile_platform_status(callback: CallbackQuery) -> None:
    data = await load_user_commercial_status(callback.from_user.id)
    vip = "Активен" if data["vip"] else "Не подключён"
    text = screen(
        "🚀 Статус CASPER",
        intro=f"<b>{data['tier']}</b> · уровень <b>{data['level']}</b>\n{_progress_bar(int(data['progress']))} {data['progress']}%",
        sections=(
            section("Прогресс", (
                metric("✨", "Опыт", f"{data['xp']}/{data['next_xp']} XP"),
                metric("💬", "Диалогов", data["dialogs"]),
                metric("🤝", "Контактов", data.get("contacts", 0)),
            )),
            section("Экономика", (
                metric("⭐", "Баланс", data["stars"]),
                metric("👑", "Premium", vip),
            )),
        ),
        footer="Уровень растёт за диалоги, активность и социальные действия. Покупка звёзд не повышает уровень.",
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Награды", callback_data="profile_hub_rewards"), InlineKeyboardButton(text="👑 Premium", callback_data="profile_hub_premium")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="profile_platform_status")],
        [InlineKeyboardButton(text="⬅️ Профиль", callback_data="profile_refresh")],
    ])
    await callback.answer("Обновлено")
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "admin_business_dashboard")
async def admin_business_dashboard(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        return
    data = await load_business_metrics()
    activation = int(data["active_24h"] * 100 / max(1, data["users"]))
    vip_share = int(data["vip"] * 100 / max(1, data["users"]))
    text = screen(
        "💼 Бизнес-показатели",
        intro="Единый коммерческий срез роста, вовлечённости, монетизации и операционного состояния.",
        sections=(
            section("Рост", (
                metric("👥", "Пользователей", data["users"]),
                metric("🆕", "Новых за 24ч", data["new_24h"]),
                metric("🟢", "Активных за 24ч", data["active_24h"]),
                metric("📈", "Доля активных", f"{activation}%"),
            )),
            section("Монетизация", (
                metric("👑", "Активных Premium", data["vip"]),
                metric("📊", "Доля Premium", f"{vip_share}%"),
                metric("⭐", "Оборот звёзд", data["stars_revenue"]),
                metric("🧾", "Покупок за 24ч", data["purchases_24h"]),
            )),
            section("Операции", (
                metric("🔎", "В очереди", data["queue"]),
                metric("💬", "Активных пар", data["active_pairs"]),
                metric("🚨", "Жалоб за 24ч", data["complaints_24h"]),
            )),
        ),
        footer="Метрики агрегированы. Содержимое переписки не используется.",
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🩺 Система", callback_data="admin_platform_health"), InlineKeyboardButton(text="📈 Аналитика", callback_data="admin_retention_dashboard")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_business_dashboard")],
        [InlineKeyboardButton(text="⬅️ Админка", callback_data="admin_back_to_panel")],
    ])
    await callback.answer("Обновлено")
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

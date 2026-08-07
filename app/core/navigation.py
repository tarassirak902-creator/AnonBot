from __future__ import annotations

from dataclasses import dataclass

from aiogram.types import InlineKeyboardButton


@dataclass(frozen=True, slots=True)
class NavigationTarget:
    callback_data: str
    label: str


PARENTS: dict[str, NavigationTarget] = {
    "main": NavigationTarget("nav_main_menu", "⬅️ Главное меню"),
    "profile": NavigationTarget("profile_refresh", "⬅️ Профиль"),
    "activity": NavigationTarget("profile_hub_activity", "⬅️ Активность"),
    "rewards": NavigationTarget("profile_hub_rewards", "⬅️ Награды"),
    "social": NavigationTarget("profile_hub_social", "⬅️ Социальное"),
    "premium": NavigationTarget("profile_hub_premium", "⬅️ Премиум"),
    "growth": NavigationTarget("growth_center", "⬅️ Центр роста"),
    "community": NavigationTarget("platform_community", "⬅️ Сообщество"),
    "daily": NavigationTarget("commercial_daily_hub", "⬅️ Мой день"),
    "admin": NavigationTarget("admin_commercial_hub", "⬅️ Управление"),
    "admin_growth": NavigationTarget("admin_growth_operations", "⬅️ Growth & Operations"),
}


def parent_target(name: str) -> NavigationTarget:
    try:
        return PARENTS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown navigation parent: {name}") from exc


def back_button(name: str, *, label: str | None = None) -> InlineKeyboardButton:
    target = parent_target(name)
    return InlineKeyboardButton(
        text=label or target.label,
        callback_data=target.callback_data,
    )

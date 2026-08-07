from __future__ import annotations

from dataclasses import dataclass

from aiogram.types import InlineKeyboardButton


@dataclass(frozen=True, slots=True)
class NavigationTarget:
    callback_data: str
    label: str


@dataclass(frozen=True, slots=True)
class ScreenContract:
    key: str
    callback_data: str
    refresh_callback: str
    parent: str | None
    back_label: str | None
    scope: str = "user"


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
    "more": NavigationTarget("commercial_more_back", "⬅️ Ещё"),
    "admin": NavigationTarget("admin_commercial_hub", "⬅️ Управление"),
    "admin_growth": NavigationTarget("admin_growth_operations", "⬅️ Growth & Operations"),
}


SCREENS: dict[str, ScreenContract] = {
    "profile": ScreenContract("profile", "profile_refresh", "profile_refresh", "main", "🏠 На главную"),
    "activity": ScreenContract("activity", "user_activity_center", "user_activity_center", "activity", "⬅️ Активность"),
    "growth": ScreenContract("growth", "growth_center", "growth_center", "daily", "⬅️ Мой день"),
    "community": ScreenContract("community", "platform_community", "platform_community", "more", "⬅️ Ещё"),
    "reputation": ScreenContract("reputation", "platform_reputation", "platform_reputation", "community", "⬅️ Сообщество"),
    "notifications": ScreenContract("notifications", "platform_notifications", "platform_notifications", "community", "⬅️ Сообщество"),
    "admin_growth": ScreenContract(
        "admin_growth", "admin_growth_operations", "admin_growth_operations", "admin", "⬅️ Управление", scope="admin"
    ),
    "admin_health": ScreenContract(
        "admin_health", "admin_platform_health", "admin_platform_health", "admin", "⬅️ Управление", scope="admin"
    ),
    "admin_retention": ScreenContract(
        "admin_retention", "admin_retention_dashboard", "admin_retention_dashboard", "admin", "⬅️ Управление", scope="admin"
    ),
    "admin_audit": ScreenContract(
        "admin_audit", "admin_audit_journal", "admin_audit_journal", "admin", "⬅️ Управление", scope="admin"
    ),
}


def parent_target(name: str) -> NavigationTarget:
    try:
        return PARENTS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown navigation parent: {name}") from exc


def screen_contract(name: str) -> ScreenContract:
    try:
        return SCREENS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown screen contract: {name}") from exc


def back_button(name: str, *, label: str | None = None) -> InlineKeyboardButton:
    target = parent_target(name)
    return InlineKeyboardButton(
        text=label or target.label,
        callback_data=target.callback_data,
    )


def screen_back_button(name: str) -> InlineKeyboardButton:
    contract = screen_contract(name)
    if contract.parent is None:
        raise ValueError(f"Screen has no parent: {name}")
    target = parent_target(contract.parent)
    return InlineKeyboardButton(
        text=contract.back_label or target.label,
        callback_data=target.callback_data,
    )


def screen_refresh_button(name: str, *, label: str = "🔄 Обновить") -> InlineKeyboardButton:
    contract = screen_contract(name)
    return InlineKeyboardButton(text=label, callback_data=contract.refresh_callback)

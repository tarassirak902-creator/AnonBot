from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove

from app.core.ui_copy import screen
from app.core.ui_labels import ButtonText


def restriction_details_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ButtonText.DETAILS, callback_data="is_banned_alert")],
    ])


def restriction_removed_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Продолжить", callback_data="restriction_removed_start")],
    ])


def warning_notice(count: int, *, auto_banned: bool = False) -> str:
    if auto_banned:
        return screen(
            "⛔ Аккаунт заблокирован",
            intro="Вы получили третье предупреждение.",
            footer="Блокировка действует бессрочно. Для уточнения обратитесь в поддержку.",
        )
    return screen(
        "⚠️ Предупреждение",
        intro=f"Администратор выдал предупреждение {count} из 3.",
        footer="Повторные нарушения могут привести к ограничению доступа.",
    )


def restriction_notice(*, permanent: bool) -> str:
    if permanent:
        return screen(
            "⛔ Доступ ограничен",
            intro="Аккаунт заблокирован администратором за нарушение правил.",
            footer="Нажмите «Подробнее», чтобы проверить статус ограничения.",
        )
    return screen(
        "🔇 Доступ временно ограничен",
        intro="Вы не можете пользоваться ботом в течение 24 часов.",
        footer="Нажмите «Подробнее», чтобы проверить оставшееся время.",
    )


def restriction_removed_notice() -> str:
    return screen(
        "✅ Ограничение снято",
        intro="Вы снова можете пользоваться ботом и искать собеседника.",
        footer="Пожалуйста, соблюдайте правила сервиса.",
    )


async def send_restriction_notice(bot, user_id: int, *, permanent: bool) -> None:
    await bot.send_message(
        user_id,
        restriction_notice(permanent=permanent),
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )
    await bot.send_message(
        user_id,
        "Статус ограничения доступен ниже.",
        reply_markup=restriction_details_keyboard(),
    )


async def notify_restriction_removed(bot, user_id: int) -> None:
    await bot.send_message(
        user_id,
        restriction_removed_notice(),
        parse_mode="HTML",
        reply_markup=restriction_removed_keyboard(),
    )


def install_moderation_notices() -> None:
    from . import callbacks_admin

    callbacks_admin._send_restriction_notice = send_restriction_notice
    callbacks_admin._notify_restriction_removed = notify_restriction_removed

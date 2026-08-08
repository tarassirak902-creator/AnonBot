from __future__ import annotations

import html

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app import database as db
from app.core.action_flow import run_state_action
from app.core.navigation import screen_back_button, screen_refresh_button
from app.core.ui_renderer import render_message
from .shared import router


def _community_keyboard(unread: int) -> InlineKeyboardMarkup:
    badge = f" ({unread})" if unread else ""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Репутация", callback_data="platform_reputation")],
        [InlineKeyboardButton(text=f"🔔 Уведомления{badge}", callback_data="platform_notifications")],
        [InlineKeyboardButton(text="🤝 Контакты", callback_data="platform_community_contacts")],
        [screen_refresh_button("community")],
        [screen_back_button("community")],
    ])


def _back_keyboard(screen_name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [screen_back_button(screen_name)],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="nav_main_menu")],
    ])


async def _community_text(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    unread = await db.unread_notification_count(user_id)
    reputation = await db.get_reputation_summary(user_id)
    text = (
        "<b>🌐 Сообщество</b>\n\n"
        f"⭐ Положительных оценок: <b>{reputation.positive_percent}%</b>\n"
        f"💬 Всего оценок: <b>{reputation.total}</b>\n"
        f"🔔 Новых уведомлений: <b>{unread}</b>\n\n"
        "Здесь собраны социальная активность, доверие и важные события аккаунта."
    )
    return text, _community_keyboard(unread)


async def _render_community(target: Message, user_id: int, *, edit: bool = False) -> None:
    text, keyboard = await _community_text(user_id)
    await render_message(target, text, reply_markup=keyboard, prefer_edit=edit)


@router.message(F.text == "🌐 Сообщество")
async def community_message(message: Message) -> None:
    await _render_community(message, message.from_user.id)


@router.callback_query(F.data == "platform_community")
async def community_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    await _render_community(callback.message, callback.from_user.id, edit=True)


@router.callback_query(F.data == "platform_reputation")
async def reputation_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    summary = await db.get_reputation_summary(callback.from_user.id)
    if summary.total >= 20 and summary.positive_percent >= 90:
        badge = "🏅 Надёжный собеседник"
    elif summary.total >= 5 and summary.positive_percent >= 75:
        badge = "✨ Хорошая репутация"
    else:
        badge = "🌱 Репутация формируется"
    await render_message(
        callback.message,
        "<b>⭐ Репутация</b>\n\n"
        f"{badge}\n\n"
        f"👍 Отлично: <b>{summary.positive}</b>\n"
        f"🙂 Нормально: <b>{summary.neutral}</b>\n"
        f"👎 Не понравилось: <b>{summary.negative}</b>\n"
        f"📊 Положительных: <b>{summary.positive_percent}%</b>\n\n"
        "Оценки принимаются только после завершённых диалогов и не раскрывают личность автора.",
        reply_markup=_back_keyboard("reputation"),
    )


async def _notifications_screen(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    items = await db.get_notifications(user_id, 10)
    if not items:
        body = "Пока нет уведомлений. Здесь появятся награды, достижения и системные события."
    else:
        lines = []
        for _id, kind, title, notification_body, is_read, created_at in items:
            marker = "▫️" if is_read else "🔹"
            lines.append(
                f"{marker} <b>{html.escape(str(title))}</b>\n"
                f"{html.escape(str(notification_body))}"
            )
        body = "\n\n".join(lines)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Прочитать всё", callback_data="platform_notifications_read")],
        [screen_refresh_button("notifications")],
        [screen_back_button("notifications")],
    ])
    return f"<b>🔔 Уведомления</b>\n\n{body}", keyboard


@router.callback_query(F.data == "platform_notifications")
async def notifications_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    text, keyboard = await _notifications_screen(callback.from_user.id)
    await render_message(callback.message, text, reply_markup=keyboard)


@router.callback_query(F.data == "platform_notifications_read")
async def notifications_read_callback(callback: CallbackQuery) -> None:
    result = {"changed": 0}

    async def action() -> bool:
        result["changed"] = await db.mark_notifications_read(callback.from_user.id)
        return result["changed"] > 0

    async def render() -> None:
        text, keyboard = await _notifications_screen(callback.from_user.id)
        if callback.message is not None:
            await render_message(callback.message, text, reply_markup=keyboard)

    await run_state_action(
        callback,
        action=action,
        render=render,
        success_text=lambda: f"Прочитано: {result['changed']}",
        noop_text="Нет непрочитанных уведомлений",
        error_text="Не удалось обновить уведомления. Попробуйте ещё раз",
    )

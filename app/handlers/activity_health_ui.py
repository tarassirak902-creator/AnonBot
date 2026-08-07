from __future__ import annotations

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.core.ui_copy import metric, screen, section
from app.services.activity_health import load_platform_health, load_user_weekly_activity
from app.services.matchmaking_service import matchmaking_health, recover_matchmaking_state

from .shared import ADMIN_IDS, db, router


def _activity_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎯 Задания", callback_data="engagement_missions"),
            InlineKeyboardButton(text="🕘 История", callback_data="community_dialog_history"),
        ],
        [
            InlineKeyboardButton(text="🤝 Контакты", callback_data="community_connections"),
            InlineKeyboardButton(text="🔄 Обновить", callback_data="user_activity_center"),
        ],
        [InlineKeyboardButton(text="⬅️ Активность", callback_data="profile_hub_activity")],
    ])


async def _activity_text(user_id: int) -> str:
    stats = await load_user_weekly_activity(user_id)
    score = min(
        100,
        stats["dialogs"] * 8
        + stats["active_days"] * 6
        + stats["ratings_given"] * 4
        + stats["mission_rewards"] * 5,
    )
    return screen(
        "⚡ Моя активность",
        intro="Личный отчёт по активности и общению за последние семь дней.",
        sections=(
            section("Общение", (
                metric("💬", "Диалогов всего", stats["dialogs"]),
                metric("✉️", "Сообщений всего", stats["messages"]),
                metric("⏱", "Минут общения", stats["chat_minutes"]),
                metric("📅", "Активных дней", f"{stats['active_days']}/7"),
            )),
            section("Вклад", (
                metric("❓", "Вопросов за неделю", stats["questions_sent"]),
                metric("✅", "Ответов за неделю", stats["questions_answered"]),
                metric("⭐", "Оценок собеседникам", stats["ratings_given"]),
                metric("🎁", "Наград за задания", stats["mission_rewards"]),
            )),
            section("Социальное", (
                metric("🤝", "Контактов", stats["contacts"]),
                metric("⚡", "Индекс активности", f"{score}/100"),
            )),
        ),
        footer="Отчёт использует только агрегаты. Тексты сообщений не сохраняются и не анализируются.",
    )


@router.callback_query(F.data == "user_activity_center")
async def user_activity_center(callback: CallbackQuery) -> None:
    await callback.answer("Обновлено")
    await callback.message.edit_text(
        await _activity_text(callback.from_user.id),
        parse_mode="HTML",
        reply_markup=_activity_keyboard(),
    )


def _health_keyboard(*, parent: str = "admin") -> InlineKeyboardMarkup:
    if parent == "growth":
        refresh = "admin_platform_health_from_growth"
        back_callback, back_label = "admin_growth_operations", "⬅️ Growth"
        ops_callback = "admin_ops_from_growth"
    elif parent == "ops_growth":
        refresh = "admin_platform_health_from_ops_growth"
        back_callback, back_label = "admin_ops_from_growth", "⬅️ Операции"
        ops_callback = "admin_ops_from_growth"
    elif parent == "ops":
        refresh = "admin_platform_health_from_ops"
        back_callback, back_label = "admin_ops_dashboard", "⬅️ Операции"
        ops_callback = "admin_ops_dashboard"
    else:
        refresh = "admin_platform_health"
        back_callback, back_label = "admin_back_to_panel", "⬅️ Админка"
        ops_callback = "admin_ops_dashboard"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data=refresh),
            InlineKeyboardButton(text="🧹 Восстановить", callback_data=f"admin_matchmaking_recover:{parent}"),
        ],
        [
            InlineKeyboardButton(text="🚨 Жалобы", callback_data="admin_complaints_dashboard"),
            InlineKeyboardButton(text="📈 Аналитика", callback_data="admin_retention_dashboard"),
        ],
        [
            InlineKeyboardButton(text="📡 Центр", callback_data=ops_callback),
            InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_user_search"),
        ],
        [InlineKeyboardButton(text=back_label, callback_data=back_callback)],
    ])


async def _health_text() -> str:
    stats = await load_platform_health()
    matchmaking = await matchmaking_health()
    problems = (
        stats["queue_stale"]
        + stats["one_sided_chats"]
        + stats["stale_chats"]
        + stats["route_errors_24h"]
        + stats["unreviewed_complaints"]
        + matchmaking["broken_links"]
        + matchmaking["self_links"]
    )
    status = "🟢 стабильно" if problems == 0 else ("🟡 внимание" if problems < 5 else "🔴 требуется проверка")
    return screen(
        "🩺 Здоровье платформы",
        intro=f"Техническое и модерационное состояние: <b>{status}</b>.",
        sections=(
            section("Матчинг", (
                metric("🔎", "В очереди", matchmaking["queue"]),
                metric("⏳", "Зависли в очереди", stats["queue_stale"]),
                metric("💬", "Активных пар", stats["active_pairs"]),
                metric("⚠️", "Невзаимных связей", matchmaking["broken_links"]),
                metric("🔁", "Самоссылок", matchmaking["self_links"]),
                metric("🕒", "Старых активных строк", stats["stale_chats"]),
            )),
            section("Надёжность", (
                metric("💥", "Ошибок маршрутов за 24ч", stats["route_errors_24h"]),
                metric("🚨", "Непроверенных жалоб", stats["unreviewed_complaints"]),
            )),
        ),
        footer="Кнопка восстановления очищает только временные битые связи и зависшую очередь. История, покупки и контакты не затрагиваются.",
    )


@router.message(F.text.in_({"🩺 Здоровье", "🩺 Система"}))
async def admin_health_message(message: Message) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer(await _health_text(), parse_mode="HTML", reply_markup=_health_keyboard())


@router.callback_query(F.data.in_({"admin_platform_health", "admin_platform_health_from_growth", "admin_platform_health_from_ops", "admin_platform_health_from_ops_growth"}))
async def admin_platform_health(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        return
    route = callback.data or ""
    if route == "admin_platform_health_from_growth":
        parent = "growth"
    elif route == "admin_platform_health_from_ops_growth":
        parent = "ops_growth"
    elif route == "admin_platform_health_from_ops":
        parent = "ops"
    else:
        parent = "admin"
    await callback.answer("Обновлено")
    await callback.message.edit_text(
        await _health_text(), parse_mode="HTML", reply_markup=_health_keyboard(parent=parent)
    )


@router.callback_query(F.data.startswith("admin_matchmaking_recover"))
async def admin_matchmaking_recover(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        return
    parent = "admin"
    if callback.data and ":" in callback.data:
        candidate = callback.data.split(":", 1)[1]
        if candidate in {"admin", "growth", "ops", "ops_growth"}:
            parent = candidate
    repaired = await recover_matchmaking_state()
    await db.log_action(
        callback.from_user.id,
        "admin_matchmaking_recovery",
        f"repaired_rows={repaired}",
    )
    await callback.answer(f"Исправлено строк: {repaired}", show_alert=True)
    await callback.message.edit_text(
        await _health_text(), parse_mode="HTML", reply_markup=_health_keyboard(parent=parent)
    )

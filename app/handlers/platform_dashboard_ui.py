from __future__ import annotations

from html import escape

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app import database as db
from app.core.action_flow import run_state_action
from app.core.ui_copy import metric, screen, section
from app.core.ui_renderer import render_callback, render_message
from app.services.platform_insights import (
    load_admin_operational_snapshot,
    load_recent_anonymous_contacts,
    remove_anonymous_contact,
)

from .shared import ADMIN_IDS, router


def _admin_ops_keyboard(*, parent: str = "admin") -> InlineKeyboardMarkup:
    if parent == "growth":
        refresh = "admin_ops_from_growth"
        back_callback, back_label = "admin_growth_operations", "⬅️ Growth"
        health_callback = "admin_platform_health_from_ops_growth"
        retention_callback = "admin_retention_from_ops_growth"
        audit_callback = "admin_audit_from_ops_growth"
        payments_callback = "admin_payment_health_from_growth"
    else:
        refresh = "admin_ops_refresh"
        back_callback, back_label = "admin_back_to_panel", "⬅️ Админка"
        health_callback = "admin_platform_health_from_ops"
        retention_callback = "admin_retention_from_ops"
        audit_callback = "admin_audit_from_ops"
        payments_callback = "admin_payment_health"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data=refresh),
            InlineKeyboardButton(text="🩺 Здоровье", callback_data=health_callback),
        ],
        [
            InlineKeyboardButton(text="📈 Удержание", callback_data=retention_callback),
            InlineKeyboardButton(text="🧾 Журнал", callback_data=audit_callback),
        ],
        [
            InlineKeyboardButton(text="💳 Платежи", callback_data=payments_callback),
            InlineKeyboardButton(text="🚨 Жалобы", callback_data="admin_complaints_dashboard"),
        ],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_user_search")],
        [InlineKeyboardButton(text="📨 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text=back_label, callback_data=back_callback)],
    ])


async def _admin_ops_text() -> str:
    stats = await load_admin_operational_snapshot()
    negative_share = 0
    if stats["ratings_24h"]:
        negative_share = round(stats["negative_ratings_24h"] * 100 / stats["ratings_24h"])
    return screen(
        "📡 Центр управления",
        intro="Живое состояние пользователей, диалогов и модерации.",
        sections=(
            section("Сейчас", (
                metric("🔎", "В очереди", stats["queue"]),
                metric("💬", "Активных связей", stats["active_chats"]),
                metric("🤝", "Взаимных контактов", stats["mutual_contacts"]),
                metric("⏳", "Ожидают взаимности", stats["pending_reconnects"]),
            )),
            section("Активность", (
                metric("🆕", "Новых за 24 часа", stats["users_24h"]),
                metric("📅", "Новых за 7 дней", stats["users_7d"]),
                metric("⭐", "Оценок за 24 часа", stats["ratings_24h"]),
                metric("👎", "Негативных оценок", f"{negative_share}%"),
            )),
            section("Безопасность", (
                metric("🚨", "Жалоб всего", stats["complaints"]),
                "При росте негативных оценок проверьте жалобы и здоровье платформы.",
            )),
        ),
        footer="Журнал показывает агрегаты действий без содержимого переписки.",
    )


@router.message(F.text.in_({"📡 Центр", "📡 Управление", "📊 Мониторинг"}))
async def admin_operations_message(message: Message) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    await render_message(
        message,
        await _admin_ops_text(),
        reply_markup=_admin_ops_keyboard(),
        prefer_edit=False,
    )


@router.callback_query(F.data.in_({"admin_ops_dashboard", "admin_ops_refresh", "admin_ops_from_growth"}))
async def admin_operations_callback(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    parent = "growth" if callback.data == "admin_ops_from_growth" else "admin"
    await render_callback(
        callback,
        await _admin_ops_text(),
        reply_markup=_admin_ops_keyboard(parent=parent),
        answer_text="Обновлено" if "refresh" in (callback.data or "") else None,
    )


async def _payment_health_screen(*, parent: str = "admin") -> tuple[str, InlineKeyboardMarkup]:
    metrics = await db.get_payment_ledger_metrics()
    issues = await db.get_recent_payment_issues(8)
    if issues:
        issue_lines = []
        for item in issues:
            marker = "❌" if item.state == "failed" else "⏳"
            detail = f" · {escape(item.last_error)}" if item.last_error else ""
            issue_lines.append(
                f"{marker} <code>{item.user_id}</code> · {escape(item.payment_type)} · "
                f"<b>{item.total_amount} ⭐</b>{detail}"
            )
        issue_body = tuple(issue_lines)
    else:
        issue_body = ("✅ Незавершённых платежей нет.",)

    text = screen(
        "💳 Платёжный контроль",
        intro="Exactly-once обработка Telegram Stars и очередь ручной сверки.",
        sections=(
            section("За 24 часа", (
                metric("✅", "Успешных платежей", metrics.completed_24h),
                metric("⭐", "Обработано Stars", metrics.completed_stars_24h),
            )),
            section("Требует внимания", (
                metric("⏳", "В обработке", metrics.processing),
                metric("❌", "С ошибкой", metrics.failed),
                metric("🧾", "Всего на сверку", metrics.unresolved),
            )),
            section("Последние незавершённые", issue_body),
        ),
        footer=(
            "Кнопка «Проверено» только закрывает ручную сверку. Она не повторяет платёж, "
            "не выдаёт товар и не разблокирует charge ID."
        ),
    )

    refresh = "admin_payment_health_from_growth" if parent == "growth" else "admin_payment_health"
    back = "admin_ops_from_growth" if parent == "growth" else "admin_ops_dashboard"
    back_label = "⬅️ Growth / Операции" if parent == "growth" else "⬅️ Центр управления"
    rows: list[list[InlineKeyboardButton]] = []
    for item in issues:
        rows.append([
            InlineKeyboardButton(
                text=f"✅ Проверено · {item.user_id} · {item.total_amount}⭐",
                callback_data=f"admin_payment_resolve:{item.ledger_id}:{parent}",
            )
        ])
    rows.append([InlineKeyboardButton(text="🔄 Обновить", callback_data=refresh)])
    rows.append([InlineKeyboardButton(text=back_label, callback_data=back)])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


async def _render_payment_health(callback: CallbackQuery, *, parent: str) -> None:
    if callback.message is None:
        return
    text, keyboard = await _payment_health_screen(parent=parent)
    await render_message(callback.message, text, reply_markup=keyboard)


@router.callback_query(F.data.in_({"admin_payment_health", "admin_payment_health_from_growth"}))
async def admin_payment_health(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    parent = "growth" if callback.data == "admin_payment_health_from_growth" else "admin"
    text, keyboard = await _payment_health_screen(parent=parent)
    await render_callback(
        callback,
        text,
        reply_markup=keyboard,
        answer_text="Платёжные данные обновлены",
    )


@router.callback_query(F.data.startswith("admin_payment_resolve:"))
async def admin_payment_resolve(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    parts = (callback.data or "").split(":")
    try:
        ledger_id = int(parts[1])
    except (IndexError, TypeError, ValueError):
        await callback.answer("Некорректная запись", show_alert=True)
        return
    parent = parts[2] if len(parts) > 2 and parts[2] in {"admin", "growth"} else "admin"
    admin_id = callback.from_user.id
    await run_state_action(
        callback,
        action=lambda: db.resolve_payment_issue(ledger_id, admin_id),
        render=lambda: _render_payment_health(callback, parent=parent),
        success_text="Сверка закрыта. Платёж повторно не исполнялся",
        noop_text="Эта сверка уже закрыта",
        error_text="Не удалось закрыть сверку",
    )


def _contacts_keyboard(items: list[dict[str, object]], *, parent: str = "social") -> InlineKeyboardMarkup:
    rows = []
    for item in items:
        rows.append([
            InlineKeyboardButton(
                text=f"🗑 Удалить {item['label']}",
                callback_data=f"community_contact_remove:{item['contact_id']}:{parent}",
            )
        ])
    if parent == "community":
        rows.append([InlineKeyboardButton(text="⬅️ Сообщество", callback_data="platform_community")])
    else:
        rows.append([InlineKeyboardButton(text="⬅️ Контакты", callback_data="community_connections")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _contacts_screen(user_id: int, *, parent: str = "social") -> tuple[str, InlineKeyboardMarkup]:
    items = await load_recent_anonymous_contacts(user_id)
    if items:
        lines = [f"• <b>{item['label']}</b>" for item in items]
        body = "\n".join(lines)
    else:
        body = "Пока нет взаимно сохранённых собеседников."
    text = (
        "<b>🤝 Мои контакты</b>\n\n"
        f"{body}\n\n"
        "Имена и Telegram-профили не раскрываются."
    )
    return text, _contacts_keyboard(items, parent=parent)


async def _render_contacts(callback: CallbackQuery, *, parent: str = "social") -> None:
    text, keyboard = await _contacts_screen(callback.from_user.id, parent=parent)
    if callback.message is not None:
        await render_message(callback.message, text, reply_markup=keyboard)


@router.callback_query(F.data == "community_contacts_list")
async def community_contacts_list(callback: CallbackQuery) -> None:
    await callback.answer()
    await _render_contacts(callback, parent="social")


@router.callback_query(F.data == "platform_community_contacts")
async def platform_community_contacts(callback: CallbackQuery) -> None:
    await callback.answer()
    await _render_contacts(callback, parent="community")


@router.callback_query(F.data.startswith("community_contact_remove:"))
async def community_contact_remove(callback: CallbackQuery) -> None:
    parts = (callback.data or "").split(":")
    try:
        contact_id = int(parts[1])
    except (IndexError, TypeError, ValueError):
        await callback.answer("Некорректный контакт", show_alert=True)
        return
    parent = parts[2] if len(parts) > 2 and parts[2] in {"social", "community"} else "social"
    user_id = callback.from_user.id

    await run_state_action(
        callback,
        action=lambda: remove_anonymous_contact(user_id, contact_id),
        render=lambda: _render_contacts(callback, parent=parent),
        success_text="Контакт удалён",
        noop_text="Контакт уже удалён",
        error_text="Не удалось удалить контакт. Попробуйте ещё раз",
    )

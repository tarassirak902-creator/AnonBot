from __future__ import annotations

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.core.ui_copy import metric, screen, section
from app.core.ui_renderer import render_callback, render_message
from app.services.engagement_service import (
    claim_daily_mission,
    load_daily_missions,
    load_retention_snapshot,
)

from .shared import ADMIN_IDS, router


def _missions_keyboard(items: list[dict[str, object]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for item in items:
        if item["claimed"]:
            text = f"✅ {item['title']}"
            callback_data = "engagement_mission_noop"
        elif item["completed"]:
            text = f"🎁 Забрать {item['reward']} ⭐"
            callback_data = f"engagement_mission_claim:{item['code']}"
        else:
            text = f"⏳ {item['progress']}/{item['target']}"
            callback_data = "engagement_mission_noop"
        rows.append([InlineKeyboardButton(text=text, callback_data=callback_data)])
    rows.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="engagement_missions")])
    rows.append([InlineKeyboardButton(text="⬅️ Награды", callback_data="profile_hub_rewards")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _mission_screen(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    items = await load_daily_missions(user_id)
    lines = []
    for item in items:
        if item["claimed"]:
            status = "✅ получено"
        elif item["completed"]:
            status = "🎁 готово"
        else:
            status = f"⏳ {item['progress']}/{item['target']}"
        lines.append(f"• <b>{item['title']}</b> — {status} · {item['reward']} ⭐")
    text = (
        "<b>🎯 Задания на сегодня</b>\n\n"
        + "\n".join(lines)
        + "\n\nЗадания обновляются каждый день. Награда начисляется только один раз."
    )
    return text, _missions_keyboard(items)


async def _render_missions(callback: CallbackQuery, *, answer_text: str | None = None, show_alert: bool = False) -> None:
    text, keyboard = await _mission_screen(callback.from_user.id)
    if answer_text is None:
        await render_callback(callback, text, reply_markup=keyboard)
        return
    await callback.answer(answer_text, show_alert=show_alert)
    if callback.message is not None:
        await render_message(callback.message, text, reply_markup=keyboard)


@router.callback_query(F.data == "engagement_missions")
async def engagement_missions(callback: CallbackQuery) -> None:
    await _render_missions(callback)


@router.callback_query(F.data == "engagement_mission_noop")
async def engagement_mission_noop(callback: CallbackQuery) -> None:
    await callback.answer("Задание ещё не выполнено" if "⏳" in (callback.message.text or "") else "Награда уже получена")


@router.callback_query(F.data.startswith("engagement_mission_claim:"))
async def engagement_mission_claim(callback: CallbackQuery) -> None:
    code = callback.data.split(":", 1)[1]
    result = await claim_daily_mission(callback.from_user.id, code)
    status = result["status"]
    if status == "ok":
        answer_text = f"Начислено {result['reward']} ⭐"
        show_alert = True
    elif status == "incomplete":
        answer_text = "Сначала выполни задание"
        show_alert = True
    elif status == "claimed":
        answer_text = "Награда уже получена"
        show_alert = False
    else:
        answer_text = "Задание не найдено"
        show_alert = True
    await _render_missions(callback, answer_text=answer_text, show_alert=show_alert)


def _retention_keyboard(*, parent: str = "admin") -> InlineKeyboardMarkup:
    if parent == "growth":
        refresh = "admin_retention_from_growth"
        back_callback, back_label = "admin_growth_operations", "⬅️ Growth"
        ops_callback = "admin_ops_from_growth"
    elif parent == "ops_growth":
        refresh = "admin_retention_from_ops_growth"
        back_callback, back_label = "admin_ops_from_growth", "⬅️ Операции"
        ops_callback = "admin_ops_from_growth"
    elif parent == "ops":
        refresh = "admin_retention_from_ops"
        back_callback, back_label = "admin_ops_dashboard", "⬅️ Операции"
        ops_callback = "admin_ops_dashboard"
    else:
        refresh = "admin_retention_dashboard"
        back_callback, back_label = "admin_back_to_panel", "⬅️ Админка"
        ops_callback = "admin_ops_dashboard"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=refresh)],
        [
            InlineKeyboardButton(text="📡 Центр", callback_data=ops_callback),
            InlineKeyboardButton(text="🚨 Жалобы", callback_data="admin_complaints_dashboard"),
        ],
        [InlineKeyboardButton(text=back_label, callback_data=back_callback)],
    ])


async def _retention_text() -> str:
    stats = await load_retention_snapshot()
    active_share = round(stats["active_7d"] * 100 / stats["users_total"]) if stats["users_total"] else 0
    dialog_share = round(stats["dialog_users"] * 100 / stats["users_total"]) if stats["users_total"] else 0
    return screen(
        "📈 Удержание и вовлечённость",
        intro="Показывает, возвращаются ли пользователи и доходят ли они до реального общения.",
        sections=(
            section("Активность", (
                metric("⚡", "Активных за 24 часа", stats["active_24h"]),
                metric("📅", "Активных за 7 дней", stats["active_7d"]),
                metric("🔁", "Вернувшихся за 7 дней", stats["returning_7d"]),
                metric("📊", "Доля активных", f"{active_share}%"),
            )),
            section("Диалоги", (
                metric("💬", "Пользователей с диалогом", stats["dialog_users"]),
                metric("🎯", "Конверсия в диалог", f"{dialog_share}%"),
            )),
            section("Задания", (
                metric("🎁", "Наград за 24 часа", stats["mission_claims_24h"]),
                metric("👥", "Участников за 7 дней", stats["mission_users_7d"]),
            )),
        ),
        footer="Метрики считаются по агрегатам. Содержимое переписки не анализируется.",
    )


@router.message(F.text.in_({"📈 Удержание", "📈 Аналитика"}))
async def admin_retention_message(message: Message) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    await render_message(
        message,
        await _retention_text(),
        reply_markup=_retention_keyboard(),
        prefer_edit=False,
    )


@router.callback_query(F.data.in_({"admin_retention_dashboard", "admin_retention_from_growth", "admin_retention_from_ops", "admin_retention_from_ops_growth"}))
async def admin_retention_dashboard(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    route = callback.data or ""
    if route == "admin_retention_from_growth":
        parent = "growth"
    elif route == "admin_retention_from_ops_growth":
        parent = "ops_growth"
    elif route == "admin_retention_from_ops":
        parent = "ops"
    else:
        parent = "admin"
    await render_callback(
        callback,
        await _retention_text(),
        reply_markup=_retention_keyboard(parent=parent),
        answer_text="Обновлено",
    )

from __future__ import annotations

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.services.engagement_service import load_daily_missions
from .shared import ADMIN_IDS, db, router


async def _user_snapshot(user_id: int) -> tuple[int, bool, int, int]:
    balance = 0
    is_vip = False
    completed = 0
    total = 0
    try:
        balance = int(await db.get_user_balance(user_id) or 0)
    except Exception:
        pass
    try:
        is_vip = bool(await db.is_user_vip(user_id))
    except Exception:
        pass
    try:
        missions = await load_daily_missions(user_id)
        total = len(missions)
        completed = sum(1 for mission in missions if getattr(mission, "completed", False))
    except Exception:
        pass
    return balance, is_vip, completed, total


def _daily_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💬 Начать чат", callback_data="start_search"),
            InlineKeyboardButton(text="🎯 Задания", callback_data="engagement_missions"),
        ],
        [
            InlineKeyboardButton(text="🎪 Событие", callback_data="weekly_event_hub"),
            InlineKeyboardButton(text="👤 Профиль", callback_data="profile_refresh"),
        ],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="commercial_daily_hub")],
        [InlineKeyboardButton(text="✖️ Закрыть", callback_data="service_message_delete")],
    ])


async def _daily_text(user_id: int) -> str:
    balance, is_vip, completed, total = await _user_snapshot(user_id)
    status = "👑 VIP" if is_vip else "🌙 Обычный"
    mission_line = f"{completed}/{total}" if total else "нет данных"
    return (
        "<b>☀️ Мой день</b>\n\n"
        f"Статус: <b>{status}</b>\n"
        f"Баланс: <b>{balance} ⭐</b>\n"
        f"Задания: <b>{mission_line}</b>\n\n"
        "Продолжи общение, забери доступные награды или открой профиль."
    )


@router.message(F.text == "☀️ Мой день")
async def commercial_daily_message(message: Message) -> None:
    await message.answer(
        await _daily_text(message.from_user.id),
        parse_mode="HTML",
        reply_markup=_daily_keyboard(),
    )


@router.callback_query(F.data == "commercial_daily_hub")
async def commercial_daily_hub(callback: CallbackQuery) -> None:
    await callback.answer("Обновлено")
    text = await _daily_text(callback.from_user.id)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=_daily_keyboard())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=_daily_keyboard())


def _admin_pulse_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📡 Операции", callback_data="admin_ops_dashboard"),
            InlineKeyboardButton(text="🩺 Система", callback_data="admin_platform_health"),
        ],
        [
            InlineKeyboardButton(text="🚨 Жалобы", callback_data="admin_complaints_dashboard"),
            InlineKeyboardButton(text="📈 Аналитика", callback_data="admin_retention_dashboard"),
        ],
        [InlineKeyboardButton(text="🧾 Журнал", callback_data="admin_audit_journal")],
        [InlineKeyboardButton(text="⬅️ Управление", callback_data="admin_commercial_hub")],
    ])


async def _admin_pulse_text() -> str:
    stats = {}
    try:
        stats = await db.get_statistics()
    except Exception:
        stats = {}
    queue = int(stats.get("queue_count", 0) or 0)
    active = int(stats.get("active_chats", 0) or 0)
    new_today = int(stats.get("new_today", 0) or 0)
    complaints = int(stats.get("total_complaints", 0) or 0)
    return (
        "<b>⚡ Пульс платформы</b>\n\n"
        f"В очереди: <b>{queue}</b>\n"
        f"Активных диалогов: <b>{active}</b>\n"
        f"Новых сегодня: <b>{new_today}</b>\n"
        f"Жалоб всего: <b>{complaints}</b>\n\n"
        "Для подробностей откройте нужный рабочий раздел."
    )


@router.callback_query(F.data == "admin_platform_pulse")
async def admin_platform_pulse(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer("Обновлено")
    text = await _admin_pulse_text()
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=_admin_pulse_keyboard())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=_admin_pulse_keyboard())

from __future__ import annotations

from datetime import datetime

import aiosqlite
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app import database as db
from app.core.ui_copy import metric, screen, section
from app.core.ui_labels import ButtonText, ScreenTitle


async def build_compact_admin_user_card(user):
    """Render a moderation-first card without the previous analytics wall."""
    uid = int(user[0])
    full_name = " ".join(part for part in (user[2], user[3]) if part).strip() or "Не указано"
    username = f"@{user[1]}" if len(user) > 1 and user[1] else "Не указан"
    joined_raw = user[4] if len(user) > 4 else None
    try:
        joined = datetime.fromisoformat(joined_raw).strftime("%d.%m.%Y") if joined_raw else "Неизвестно"
    except (TypeError, ValueError):
        joined = str(joined_raw or "Неизвестно")

    blocked = bool(user[5]) if len(user) > 5 else False
    warnings = int(user[6] or 0) if len(user) > 6 else 0
    complaints = int(user[9] or 0) if len(user) > 9 else 0
    is_vip = bool(user[17]) if len(user) > 17 else False
    last_activity_raw = user[20] if len(user) > 20 else None
    completed_dialogs = int(user[22] or 0) if len(user) > 22 else 0

    try:
        last_activity = datetime.fromisoformat(last_activity_raw).strftime("%d.%m.%Y, %H:%M") if last_activity_raw else "Неизвестно"
    except (TypeError, ValueError):
        last_activity = str(last_activity_raw or "Неизвестно")

    async with aiosqlite.connect(db.DB_PATH, timeout=10) as connection:
        async def scalar(sql: str, params=()):
            row = await (await connection.execute(sql, params)).fetchone()
            return int((row[0] if row else 0) or 0)

        questions_received = await scalar(
            "SELECT COUNT(*) FROM anonymous_questions WHERE receiver_id=?", (uid,)
        )
        questions_sent = await scalar(
            "SELECT COUNT(*) FROM anonymous_questions WHERE sender_id=?", (uid,)
        )
        purchases = await scalar("SELECT COUNT(*) FROM purchases WHERE buyer_id=?", (uid,))
        spent = await scalar(
            "SELECT COALESCE(SUM(price_stars),0) FROM purchases WHERE buyer_id=?", (uid,)
        )

    state_label = "Заблокирован" if blocked else "Активен"
    vip_label = "Активен" if is_vip else "Нет"
    text = screen(
        ScreenTitle.USER_CARD,
        sections=(
            section("Основное", [
                metric("🆔", "ID", uid),
                metric("👤", "Имя", full_name),
                metric("🔗", "Username", username),
                metric("📅", "Регистрация", joined),
                metric("🕒", "Последняя активность", last_activity),
            ]),
            section("Активность", [
                metric("💬", "Диалоги", completed_dialogs),
                metric("📥", "Вопросы получены", questions_received),
                metric("📤", "Вопросы отправлены", questions_sent),
                metric("🛍", "Покупки", purchases),
                metric("⭐", "Потрачено", f"{spent} ⭐"),
            ]),
            section("Модерация", [
                metric("🛡", "Статус", state_label),
                metric("👑", "VIP", vip_label),
                metric("⚠️", "Предупреждения", f"{warnings}/3"),
                metric("🚨", "Жалобы", complaints),
            ]),
        ),
        footer="Подробные события доступны в истории пользователя.",
    )

    vip_text = "❌ Снять VIP" if is_vip else "👑 Выдать VIP"
    vip_callback = f"admin_cancel_vip_{uid}" if is_vip else f"admin_confirm_vip_{uid}"
    warning_buttons = [InlineKeyboardButton(text="⚠️ Предупредить", callback_data=f"warn_{uid}")]
    if warnings:
        warning_buttons.append(
            InlineKeyboardButton(text=f"➖ Снять ({warnings})", callback_data=f"admin_unwarn_{uid}")
        )

    rows = [[InlineKeyboardButton(text=vip_text, callback_data=vip_callback)], warning_buttons]
    if blocked:
        rows.append([InlineKeyboardButton(text=ButtonText.UNBLOCK, callback_data=f"admin_unblock_{uid}")])
    else:
        rows.append([
            InlineKeyboardButton(text="🔇 Мут 24 ч.", callback_data=f"admin_confirm_mute_{uid}"),
            InlineKeyboardButton(text=ButtonText.BLOCK, callback_data=f"admin_confirm_ban_{uid}"),
        ])
    rows.extend([
        [
            InlineKeyboardButton(text=ButtonText.HISTORY, callback_data=f"admin_user_history_{uid}"),
            InlineKeyboardButton(text=ButtonText.REFRESH, callback_data=f"admin_user_card_{uid}"),
        ],
        [InlineKeyboardButton(text=ButtonText.BACK, callback_data="admin_back_to_users")],
    ])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def install_admin_card_ui() -> None:
    """Patch the legacy shared boundary before callback modules import it."""
    from . import shared

    shared.admin_user_card = build_compact_admin_user_card

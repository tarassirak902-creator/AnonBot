from __future__ import annotations

import html
from datetime import datetime

import aiosqlite
from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.core.ui_copy import metric, screen, section
from app.core.ui_labels import ButtonText

from .shared import ADMIN_IDS, db, router


def _back_to_users() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ButtonText.BACK, callback_data="admin_back_to_users")]
    ])


def _user_label(first_name: str | None, last_name: str | None, username: str | None) -> str:
    name = " ".join(part for part in (first_name, last_name) if part).strip() or "Без имени"
    username_text = f"@{username}" if username else "без username"
    return f"{html.escape(name)} · {html.escape(username_text)}"


@router.callback_query(F.data == "admin_warned_list")
async def admin_warned_list_ui(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer()
    async with aiosqlite.connect(db.DB_PATH) as connection:
        rows = await (await connection.execute(
            "SELECT user_id, username, first_name, last_name, warnings "
            "FROM users WHERE warnings > 0 ORDER BY warnings DESC LIMIT 50"
        )).fetchall()

    if not rows:
        text = screen("⚠️ Предупреждения", intro="Пользователей с предупреждениями нет.")
    else:
        items = [
            f"<b>{index}. {_user_label(first, last, username)}</b>\n"
            f"🆔 <code>{uid}</code> · ⚠️ <b>{warnings}/3</b>"
            for index, (uid, username, first, last, warnings) in enumerate(rows, 1)
        ]
        text = screen(
            "⚠️ Предупреждения",
            sections=(section("Пользователи", items),),
            footer=f"Показано: {len(rows)}",
        )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=_back_to_users())


@router.callback_query(F.data == "admin_restricted_list")
async def admin_restricted_list_ui(callback: CallbackQuery) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer()
    async with aiosqlite.connect(db.DB_PATH) as connection:
        rows = await (await connection.execute(
            "SELECT user_id, username, first_name, last_name, blocked_until "
            "FROM users WHERE blocked=1 "
            "ORDER BY CASE WHEN blocked_until IS NULL THEN 0 ELSE 1 END, blocked_until DESC LIMIT 50"
        )).fetchall()

    if not rows:
        text = screen("🔒 Ограничения", intro="Активных ограничений нет.")
    else:
        items = []
        for uid, username, first, last, blocked_until in rows:
            if blocked_until:
                try:
                    until = datetime.fromisoformat(blocked_until).strftime("%d.%m.%Y %H:%M")
                except (TypeError, ValueError):
                    until = str(blocked_until)
                status = f"до <b>{html.escape(until)}</b>"
            else:
                status = "<b>бессрочно</b>"
            items.append(
                f"<b>{_user_label(first, last, username)}</b>\n"
                f"🆔 <code>{uid}</code> · 🔒 {status}"
            )
        text = screen(
            "🔒 Ограничения",
            sections=(section("Пользователи", items),),
            footer=f"Показано: {len(rows)}",
        )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=_back_to_users())


@router.message(F.text == "💸 Заявки на вывод")
async def admin_withdrawals_ui(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    rows = await db.get_pending_withdraw_requests()
    if not rows:
        await message.answer(screen("💸 Заявки на вывод", intro="Новых заявок нет."), parse_mode="HTML")
        return

    await message.answer(
        screen("💸 Заявки на вывод", intro=f"Ожидают обработки: <b>{len(rows)}</b>."),
        parse_mode="HTML",
    )
    for req_id, uid, amount, created_at, username, first_name, last_name in rows:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"withdraw_approve_{req_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"withdraw_reject_{req_id}"),
        ]])
        text = screen(
            f"💸 Заявка №{req_id}",
            sections=(section("Данные", (
                metric("👤", "Пользователь", _user_label(first_name, last_name, username)),
                metric("🆔", "ID", uid),
                metric("⭐", "Сумма", f"{amount} ⭐"),
                metric("🕒", "Создана", created_at or "Не указано"),
            )),),
        )
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

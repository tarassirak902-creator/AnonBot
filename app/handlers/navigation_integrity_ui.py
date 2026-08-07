from __future__ import annotations

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from .events_audit_ui import _audit_text
from .shared import ADMIN_IDS, router


@router.callback_query(F.data == "admin_audit_from_ops_growth")
async def admin_audit_from_ops_growth(callback: CallbackQuery) -> None:
    """Open audit from Growth -> Operations without losing the parent chain."""
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer("Обновлено")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_audit_from_ops_growth")],
        [InlineKeyboardButton(text="⬅️ Операции", callback_data="admin_ops_from_growth")],
    ])
    text = await _audit_text()
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)

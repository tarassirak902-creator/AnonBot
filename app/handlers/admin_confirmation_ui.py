from __future__ import annotations

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.core.action_ui import confirmation_screen
from app.core.ui_labels import ButtonText

from .shared import ADMIN_IDS, router


def _confirmation_keyboard(*, confirm_text: str, confirm_callback: str, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=confirm_text, callback_data=confirm_callback),
            InlineKeyboardButton(text=ButtonText.CANCEL, callback_data=f"admin_user_card_{user_id}"),
        ],
    ])


async def _show_confirmation(
    callback: CallbackQuery,
    *,
    title: str,
    description: str,
    confirm_text: str,
    confirm_callback: str,
    user_id: int,
) -> None:
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer()
    await callback.message.edit_text(
        confirmation_screen(title, description, danger=True),
        parse_mode="HTML",
        reply_markup=_confirmation_keyboard(
            confirm_text=confirm_text,
            confirm_callback=confirm_callback,
            user_id=user_id,
        ),
    )


@router.callback_query(F.data.startswith("admin_confirm_vip_"))
async def confirm_vip_ui(callback: CallbackQuery) -> None:
    user_id = int(callback.data.rsplit("_", 1)[1])
    await _show_confirmation(
        callback,
        title="Выдать VIP",
        description=f"Пользователь <code>{user_id}</code> получит VIP на 30 дней.",
        confirm_text="✅ Выдать VIP",
        confirm_callback=f"admin_give_vip_{user_id}",
        user_id=user_id,
    )


@router.callback_query(F.data.startswith("admin_confirm_mute_"))
async def confirm_mute_ui(callback: CallbackQuery) -> None:
    user_id = int(callback.data.rsplit("_", 1)[1])
    await _show_confirmation(
        callback,
        title="Ограничить пользователя",
        description=f"Пользователь <code>{user_id}</code> не сможет пользоваться ботом 24 часа.",
        confirm_text="✅ Ограничить на 24 часа",
        confirm_callback=f"admin_do_mute_{user_id}",
        user_id=user_id,
    )


@router.callback_query(F.data.startswith("admin_confirm_ban_"))
async def confirm_ban_ui(callback: CallbackQuery) -> None:
    user_id = int(callback.data.rsplit("_", 1)[1])
    await _show_confirmation(
        callback,
        title="Заблокировать пользователя",
        description=f"Пользователь <code>{user_id}</code> будет заблокирован бессрочно.",
        confirm_text="⛔ Заблокировать",
        confirm_callback=f"admin_do_ban_{user_id}",
        user_id=user_id,
    )

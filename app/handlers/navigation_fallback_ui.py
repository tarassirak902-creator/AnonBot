from __future__ import annotations

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from .profile_view import send_profile_screen
from .shared import ADMIN_IDS, main_menu, pending_invoice_message_ids, router


@router.callback_query(F.data == "nav_main_menu")
async def nav_main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Return to a usable reply keyboard and clear transient payment UI state."""
    await state.clear()
    pending_invoice_message_ids.pop(callback.from_user.id, None)
    await callback.answer()
    await callback.message.answer(
        "🏠 <b>Главное меню</b>\n\nВыберите нужный раздел.",
        parse_mode="HTML",
        reply_markup=main_menu(callback.from_user.id in ADMIN_IDS),
    )


@router.callback_query(F.data.in_({"nav_profile_home", "profile_hub_back"}))
async def nav_profile_home(callback: CallbackQuery, state: FSMContext) -> None:
    """Provide one stable profile return route for nested commercial screens."""
    await state.clear()
    await callback.answer()
    result = await send_profile_screen(callback.message, callback.from_user.id)
    if result is None:
        await callback.message.answer(
            "⚠️ Профиль пока недоступен. Вернитесь в главное меню.",
            reply_markup=main_menu(callback.from_user.id in ADMIN_IDS),
        )

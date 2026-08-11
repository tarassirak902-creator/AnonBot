from __future__ import annotations

from types import SimpleNamespace

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from . import questions
from .shared import ADMIN_IDS, Broadcast, router, start_searching


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_entry(callback: CallbackQuery, state: FSMContext) -> None:
    """Open the broadcast composer from inline admin dashboards."""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    await state.clear()
    await callback.answer()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="↩️ Назад", callback_data="admin_back_to_panel")]
        ]
    )
    text = "Отправьте сообщение для рассылки (текст, фото, видео, голосовое и т.д.):"
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard)
    await state.set_state(Broadcast.waiting_for_message)


@router.callback_query(F.data == "start_search")
async def start_search_from_inline(callback: CallbackQuery, state: FSMContext) -> None:
    """Start matchmaking from inline CTA screens using the real callback user."""
    await state.clear()
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

    # start_searching only needs from_user, bot and answer from its Message-like input.
    # callback.message.from_user is the bot itself, so provide the callback initiator
    # explicitly instead of accidentally queueing the bot account.
    message_adapter = SimpleNamespace(
        from_user=callback.from_user,
        bot=callback.bot,
        answer=callback.message.answer,
    )
    await start_searching(message_adapter)


@router.message(F.text.startswith("❓ Написать "))
async def legacy_personal_question_button(message: Message, state: FSMContext) -> None:
    """Keep the legacy personal-link reply keyboard compatible with its target flow."""
    await questions.open_question_target_from_menu(message, state)

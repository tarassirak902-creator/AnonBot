from __future__ import annotations

from datetime import datetime

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.core.ui_copy import screen

from .shared import (
    ADMIN_IDS,
    cancel_inactivity_timer,
    cancel_search_timer,
    cancel_unread_reminder,
    db,
    main_menu,
    notify_pending_question_activity,
    reveal_offer_kb,
    router,
    send_brand_card,
    start_searching,
)


async def _finish_dialog(message: Message, *, find_next: bool) -> None:
    user_id = message.from_user.id
    cancel_search_timer(user_id)

    await db.add_completed_chat_time(user_id)
    partner_id = await db.end_chat(user_id)
    if partner_id:
        await db.add_completed_chat_time(partner_id)

    cancel_inactivity_timer(user_id, partner_id)
    cancel_unread_reminder(user_id)
    if partner_id:
        cancel_unread_reminder(partner_id)

    if not partner_id:
        if find_next:
            await db.remove_from_queue(user_id)
            await message.answer(
                screen(
                    "🔄 Ищем нового собеседника",
                    intro="Предыдущий диалог уже завершён.",
                ),
                parse_mode="HTML",
            )
            await start_searching(message)
        else:
            await message.answer(
                screen(
                    "🏠 Вы уже в главном меню",
                    intro="Активного диалога сейчас нет.",
                    footer="Начните новое общение первой кнопкой.",
                ),
                parse_mode="HTML",
                reply_markup=main_menu(user_id in ADMIN_IDS),
            )
        return

    try:
        await message.bot.send_message(
            partner_id,
            screen(
                "👋 Диалог завершён",
                intro="Собеседник закончил общение.",
                footer="Вы можете сразу начать новый поиск.",
            ),
            parse_mode="HTML",
            reply_markup=main_menu(partner_id in ADMIN_IDS),
        )
    except Exception:
        pass

    await send_brand_card(
        message,
        "dialog_ended",
        screen(
            "🔄 Ищу нового собеседника" if find_next else "👋 Диалог завершён",
            intro=(
                "Предыдущий диалог закрыт. Новый поиск уже запускается."
                if find_next
                else "Вы завершили общение и вернулись в главное меню."
            ),
        ),
        main_menu(user_id in ADMIN_IDS) if not find_next else None,
    )

    try:
        from .advertising import send_ads_to_dialog_users

        await send_ads_to_dialog_users(
            message.bot,
            user_id,
            partner_id,
            f"manual:{min(user_id, partner_id)}:{max(user_id, partner_id)}:{int(datetime.now().timestamp())}",
        )
        await message.bot.send_message(
            partner_id,
            "Хотите узнать, кто был вашим собеседником?",
            reply_markup=reveal_offer_kb(user_id),
        )
        await message.answer(
            "Хотите раскрыть профиль прошлого собеседника?",
            reply_markup=reveal_offer_kb(partner_id),
        )
    except Exception:
        pass

    await db.log_action(user_id, "dialog_end", f"with {partner_id}")
    await notify_pending_question_activity(message.bot, user_id)
    await notify_pending_question_activity(message.bot, partner_id)

    if find_next:
        await start_searching(message)


@router.message(F.text.in_({"➡️ Новый собеседник", "➡️ Следующий собеседник"}))
async def next_partner_ui(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _finish_dialog(message, find_next=True)


@router.message(F.text.in_({"⏹ Завершить", "❌ Завершить диалог"}))
async def end_dialog_ui(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _finish_dialog(message, find_next=False)

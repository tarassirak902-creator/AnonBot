from __future__ import annotations

from datetime import datetime, timezone

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.core.ui_copy import screen
from app.database.platform_automation_repository import build_dialog_key, create_rating_pair
from app.database.platform_missions_repository import record_mission_event

from .platform_automation_ui import send_rating_prompt
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


async def _send_rating_prompts(bot, user_id: int, partner_id: int, dialog_key: str) -> None:
    """Create one rating token per participant and deliver prompts best-effort."""
    try:
        first, second = await create_rating_pair(user_id, partner_id, dialog_key=dialog_key)
    except Exception:
        return
    for pending in (first, second):
        try:
            await send_rating_prompt(bot, pending)
        except Exception:
            # The token remains valid for the other participant and expires safely.
            pass


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

    ended_at = datetime.now(timezone.utc)
    dialog_key = build_dialog_key(user_id, partner_id, ended_at)

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
            f"manual:{dialog_key}",
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

    await _send_rating_prompts(message.bot, user_id, partner_id, dialog_key)
    await record_mission_event(user_id, f"dialog:{dialog_key}:{user_id}", "dialog_complete")
    await record_mission_event(partner_id, f"dialog:{dialog_key}:{partner_id}", "dialog_complete")

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

from __future__ import annotations

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.core.ui_copy import screen

from . import shared
from .shared import (
    ADMIN_IDS,
    cancel_search_timer,
    db,
    delete_search_card,
    main_menu,
    router,
    start_searching,
)


def install_search_copy() -> None:
    """Replace search-card captions without changing matching or timer logic."""
    shared.SEARCH_CAPTIONS.update(
        {
            "start": screen(
                "🔎 Поиск собеседника",
                intro="Ищу свободного собеседника.",
                footer="Обычно это занимает несколько секунд.",
            ),
            "waiting": screen(
                "⏳ Поиск продолжается",
                intro="Подходящий собеседник пока не найден.",
                footer="Можно подождать или отменить поиск.",
            ),
            "found": screen(
                "💬 Собеседник найден",
                intro="Диалог начался. Общайтесь уважительно и не передавайте личные данные.",
            ),
            "timeout": screen(
                "⌛ Поиск остановлен",
                intro="За отведённое время собеседник не нашёлся.",
                footer="Запустите поиск снова, когда будете готовы.",
            ),
        }
    )


@router.message(F.text == "💬 Найти собеседника")
async def search_start_ui(message: Message, state: FSMContext) -> None:
    await state.clear()
    await start_searching(message)


@router.message(F.text.in_({"❌  Отменить поиск", "❌ Отменить поиск"}))
async def cancel_search_ui(message: Message, state: FSMContext) -> None:
    await state.clear()
    user_id = message.from_user.id
    cancel_search_timer(user_id)
    await delete_search_card(message.bot, user_id)
    await db.remove_from_queue(user_id)
    await db.log_action(user_id, "queue_leave", "user_cancelled")
    await message.answer(
        screen(
            "✅ Поиск остановлен",
            intro="Вы вышли из очереди.",
            footer="Можно запустить новый поиск в любое время.",
        ),
        parse_mode="HTML",
        reply_markup=main_menu(user_id in ADMIN_IDS),
    )

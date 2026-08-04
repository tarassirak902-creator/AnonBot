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
                "🚀 Поиск запущен",
                intro="CASPER подбирает свободного собеседника прямо сейчас.",
                footer="Оставайтесь в боте — сообщение появится сразу после совпадения.",
            ),
            "waiting": screen(
                "⏳ Всё ещё ищем",
                intro="Свободный собеседник пока не найден.",
                footer="Можно продолжить ждать, сыграть с CASPER или остановить поиск.",
            ),
            "found": screen(
                "✨ Собеседник найден",
                intro="Анонимный диалог уже начался.",
                footer="Будьте уважительны и не отправляйте личные данные незнакомцам.",
            ),
            "timeout": screen(
                "⌛ Сейчас никого нет",
                intro="За отведённое время подходящий собеседник не нашёлся.",
                footer="Вернитесь в главное меню и попробуйте снова чуть позже.",
            ),
        }
    )


@router.message(F.text.in_({"🚀 Начать общение", "💬 Найти собеседника"}))
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
            intro="Вы вышли из очереди и вернулись в главное меню.",
            footer="Новый поиск можно запустить первой кнопкой.",
        ),
        parse_mode="HTML",
        reply_markup=main_menu(user_id in ADMIN_IDS),
    )

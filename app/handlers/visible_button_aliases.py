from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from .shared import router
from . import (
    advertising,
    admin_overview_ui,
    commands,
    commercial_daily_hub,
    commercial_navigation_ui,
    dialog_ui,
    menus,
    questions,
)


@router.message(F.text.in_({"💬 Чат", "🚀 Начать общение"}))
async def route_search(message: Message, state: FSMContext) -> None:
    await menus.search_start(message, state)


@router.message(F.text == "❌ Отменить поиск")
async def route_cancel_search(message: Message, state: FSMContext) -> None:
    await menus.cancel_search_handler(message, state)


@router.message(F.text.in_({"❓ Вопросы", "❓ Анонимные вопросы"}))
async def route_questions(message: Message, state: FSMContext) -> None:
    await state.clear()
    await questions._send_questions_home(message, state)


@router.message(F.text.in_({"🎮 Игры", "🎮 Мини-игры", "Мини игры"}))
async def route_games(message: Message, state: FSMContext) -> None:
    await menus.solo_games_start_menu(message, state)


@router.message(F.text.in_({"👤 Профиль", "👤 Моя анкета", "⚙️ Профиль"}))
async def route_profile(message: Message, state: FSMContext) -> None:
    await menus.profile(message, state)


@router.message(F.text.in_({"🎁 Друзья", "🎁 Пригласить друга", "👥 Пригласить друга", "🔗 Пригласить друга"}))
async def route_invite(message: Message, state: FSMContext) -> None:
    await commands.invite_friend(message, state)


@router.message(F.text == "☀️ Мой день")
async def route_daily_hub(message: Message) -> None:
    await commercial_daily_hub.commercial_daily_message(message)


@router.message(F.text == "✨ Ещё")
async def route_more(message: Message) -> None:
    await commercial_navigation_ui.commercial_more(message)


@router.message(F.text.in_({"📣 Реклама", "📣 Разместить рекламу", "📣 Купить рекламу", "📢 Купить рекламу", "📢 Реклама в CASPER"}))
async def route_advertising(message: Message, state: FSMContext) -> None:
    await advertising.advertising_menu(message, state)


@router.message(F.text.in_({"⚙️ Админка", "⚙️ Панель управления"}))
async def route_admin_panel(message: Message, state: FSMContext) -> None:
    await admin_overview_ui.admin_panel_entry(message, state)


@router.message(F.text == "➡️ Новый")
async def route_next_partner(message: Message, state: FSMContext) -> None:
    await dialog_ui.next_partner_ui(message, state)


@router.message(F.text == "🎮 Дуэль")
async def route_duel(message: Message, state: FSMContext) -> None:
    await menus.duel_games_start_menu(message, state)


@router.message(F.text == "🎁 Подарок")
async def route_chat_gift(message: Message) -> None:
    await menus.show_gifts(message)


@router.message(F.text.in_({"👤 Раскрыть", "👤 Кто это?"}))
async def route_reveal(message: Message) -> None:
    await menus.reveal_partner(message)


@router.message(F.text == "🚨 Жалоба")
async def route_complaint(message: Message) -> None:
    await menus.complaint_menu(message)

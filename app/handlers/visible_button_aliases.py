from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from .shared import router
from . import menus


@router.message(F.text == "🚀 Начать общение")
async def redesigned_search(message: Message, state: FSMContext) -> None:
    await menus.search_start(message, state)


@router.message(F.text == "🎮 Игры")
async def redesigned_games(message: Message, state: FSMContext) -> None:
    await menus.solo_games_start_menu(message, state)


@router.message(F.text == "👤 Профиль")
async def redesigned_profile(message: Message, state: FSMContext) -> None:
    await menus.profile(message, state)


@router.message(F.text == "🎮 Дуэль")
async def redesigned_duel(message: Message, state: FSMContext) -> None:
    await menus.duel_games_start_menu(message, state)


@router.message(F.text == "🎁 Подарок")
async def redesigned_chat_gift(message: Message) -> None:
    await menus.show_gifts(message)


@router.message(F.text == "👤 Кто это?")
async def redesigned_reveal(message: Message) -> None:
    await menus.reveal_partner(message)


@router.message(F.text == "🚨 Жалоба")
async def redesigned_complaint(message: Message) -> None:
    await menus.complaint_menu(message)

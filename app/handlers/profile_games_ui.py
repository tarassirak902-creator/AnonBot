from __future__ import annotations

import time

from .shared import *
from .casper_game import MAX_ATTEMPTS_PER_SEARCH, open_casper_board
from .profile_view import send_profile_screen

@router.message(F.text.in_({"👤 Профиль", "⚙️ Профиль", "👤 Моя анкета"}))
async def profile_entry(message: Message, state: FSMContext) -> None:
    await state.clear()
    await hide_reply_keyboard(message)
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        u = message.from_user
        await db.add_user(u.id, u.username, u.first_name, u.last_name)
    await send_profile_screen(message, user_id)

@router.message(F.text.in_({"🎮 Игры", "Мини игры", "🎮 Мини-игры"}))
async def solo_games_entry(message: Message, state: FSMContext) -> None:
    await state.clear()
    await hide_reply_keyboard(message)
    await send_brand_card(message, "games", "🎮 <b>Мини-игры CASPER</b>\n\nВыберите одиночную игру против CASPER на ⭐ Звёзды:", solo_games_menu_kb())

@router.message(F.text.in_({"🎮 Дуэль", "⚔️ Играть с собеседником"}))
async def duel_games_entry(message: Message, state: FSMContext) -> None:
    await state.clear()
    if not await db.get_partner(message.from_user.id):
        await message.answer("Дуэли доступны только во время активного диалога.")
        return
    await message.answer("⚔️ <b>Выберите режим дуэли с собеседником:</b>", parse_mode="HTML", reply_markup=duel_games_menu_kb())

@router.message(F.text == "👻 Поймать CASPER")
async def search_casper_game_entry(message: Message) -> None:
    user_id = message.from_user.id
    if await db.get_partner(user_id):
        await message.answer("💬 Собеседник уже найден — игра завершена.", reply_markup=chat_menu())
        return
    if not await db.is_in_queue(user_id):
        await message.answer("👻 Играть здесь можно только во время поиска собеседника.", reply_markup=main_menu(user_id in ADMIN_IDS))
        return
    attempts = search_game_attempts.get(user_id, 0)
    if attempts >= MAX_ATTEMPTS_PER_SEARCH:
        await message.answer(f"⏳ Вы использовали все {MAX_ATTEMPTS_PER_SEARCH} попыток этого поиска.\n\nCASPER продолжает искать вам собеседника.", reply_markup=cancel_search_menu())
        return
    now = time.monotonic()
    cooldown_left = 3.0 - (now - search_game_last_spin.get(user_id, 0.0))
    if cooldown_left > 0:
        await message.answer(f"⏳ Подождите ещё {max(1, int(cooldown_left + 0.9))} сек.")
        return
    search_game_last_spin[user_id] = now
    attempts += 1
    search_game_attempts[user_id] = attempts
    await open_casper_board(message=message, attempt_no=attempts)

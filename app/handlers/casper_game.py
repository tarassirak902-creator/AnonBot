from __future__ import annotations

import asyncio
import random
import secrets
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from aiogram import F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app import database as db
from .shared import (
    router,
    search_game_attempts,
)


RewardType = Literal["vip", "discount", "star", "empty"]
GameResult = Literal["vip", "discount", "star", "casper", "draw"]

MAX_ATTEMPTS_PER_SEARCH = 30
PICKS_PER_GAME = 5
STAR_REWARD_AMOUNT = 25
STAR_DAILY_LIMIT = 25
BOARD_SIZE = 25
BOARD_COLUMNS = 5


@dataclass
class CasperRound:
    token: str
    user_id: int
    message_id: int
    game_no: int
    planned_result: GameResult
    symbols: list[str]
    opened_cells: dict[int, str] = field(default_factory=dict)
    revealed_cells: dict[int, str] = field(default_factory=dict)
    finished: bool = False


# Скрытые реальные вероятности на одну партию из 1 000 000.
# Скидка выпадает чаще звёзд. Пользователю проценты не показываются.
REWARD_TABLES = {
    1: {
        "vip": 10,           # 0,001%
        "discount": 10_000,  # 1%
        "star": 200,         # 0,02%
    },
    2: {
        "vip": 30,           # 0,003%
        "discount": 15_000,  # 1,5%
        "star": 500,         # 0,05%
    },
    3: {
        "vip": 80,           # 0,008%
        "discount": 20_000,  # 2%
        "star": 1_000,       # 0,1%
    },
}


casper_rounds: dict[int, CasperRound] = {}
casper_game_message_ids: dict[int, int] = {}
casper_round_locks: dict[int, asyncio.Lock] = {}


def _attempt_tier(game_no: int) -> int:
    if game_no <= 10:
        return 1
    if game_no <= 20:
        return 2
    return 3


def _stars_won_today(state: dict) -> int:
    today = datetime.now().date().isoformat()

    if state.get("stars_date") != today:
        return 0

    return int(state.get("stars_today") or 0)


async def _available_rewards(user_id: int) -> dict[str, bool]:
    state = await db.get_search_game_reward_state(user_id)

    return {
        "vip": await db.can_win_search_game_vip(user_id),
        "discount": not await db.has_search_game_discount(user_id),
        "star": (
            _stars_won_today(state) + STAR_REWARD_AMOUNT
            <= STAR_DAILY_LIMIT
        ),
    }


async def select_game_result(
    user_id: int,
    game_no: int,
) -> GameResult:
    safe_game_no = max(
        1,
        min(int(game_no), MAX_ATTEMPTS_PER_SEARCH),
    )

    table = REWARD_TABLES[_attempt_tier(safe_game_no)]
    available = await _available_rewards(user_id)

    roll = secrets.randbelow(1_000_000) + 1

    vip_end = table["vip"]
    discount_end = vip_end + table["discount"]
    star_end = discount_end + table["star"]

    if roll <= vip_end:
        return "vip" if available["vip"] else _empty_result()

    if roll <= discount_end:
        return (
            "discount"
            if available["discount"]
            else _empty_result()
        )

    if roll <= star_end:
        return "star" if available["star"] else _empty_result()

    return _empty_result()


def _empty_result() -> GameResult:
    # Если ценная награда не выпала, партия заканчивается
    # либо победой CASPER, либо ничьёй.
    return "casper" if secrets.randbelow(100) < 15 else "draw"


def _build_symbols(result: GameResult) -> list[str]:
    """
    Создаёт последовательность из пяти открытий.

    Три одинаковых призовых символа означают победу.
    Три призрака означают победу CASPER.
    При ничьей ни один символ не встречается трижды.
    """
    if result == "vip":
        symbols = ["👑", "👑", "👑", "💜", "👻"]
    elif result == "discount":
        symbols = ["💜", "💜", "💜", "👻", "⭐"]
    elif result == "star":
        symbols = ["⭐", "⭐", "⭐", "👻", "💜"]
    elif result == "casper":
        symbols = ["👻", "👻", "👻", "💜", "⭐"]
    else:
        draw_variants = (
            ["👻", "👻", "💜", "💜", "⭐"],
            ["👻", "👻", "⭐", "⭐", "💜"],
            ["💜", "💜", "⭐", "⭐", "👻"],
            ["👑", "👑", "💜", "💜", "👻"],
        )
        symbols = list(random.SystemRandom().choice(draw_variants))

    random.SystemRandom().shuffle(symbols)
    return symbols


def _board_keyboard(
    round_data: CasperRound,
    *,
    show_replay: bool = False,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for row_start in range(0, BOARD_SIZE, BOARD_COLUMNS):
        row = []

        for index in range(
            row_start,
            min(row_start + BOARD_COLUMNS, BOARD_SIZE),
        ):
            if round_data.finished:
                if not round_data.revealed_cells:
                    target_counts = {
                        "👑": 5,
                        "💜": 8,
                        "⭐": 7,
                        "👻": 5,
                    }

                    round_data.revealed_cells.update(
                        round_data.opened_cells
                    )

                    for symbol in round_data.opened_cells.values():
                        target_counts[symbol] -= 1

                    remaining_symbols = []

                    for symbol, amount in target_counts.items():
                        remaining_symbols.extend(
                            [symbol] * amount
                        )

                    random.SystemRandom().shuffle(
                        remaining_symbols
                    )

                    unopened_indexes = [
                        cell_index
                        for cell_index in range(BOARD_SIZE)
                        if cell_index
                        not in round_data.opened_cells
                    ]

                    for cell_index, symbol in zip(
                        unopened_indexes,
                        remaining_symbols,
                    ):
                        round_data.revealed_cells[
                            cell_index
                        ] = symbol

                text = round_data.revealed_cells[index]
                callback_data = "casper_round_closed"

            elif index in round_data.opened_cells:
                text = round_data.opened_cells[index]
                callback_data = "casper_opened_cell"

            else:
                text = "❓"
                callback_data = (
                    f"casper_pick:{round_data.token}:{index}"
                )

            row.append(
                InlineKeyboardButton(
                    text=text,
                    callback_data=callback_data,
                )
            )

        rows.append(row)

    if show_replay:
        rows.append([
            InlineKeyboardButton(
                text="👻 Сыграть ещё",
                callback_data="casper_play_again",
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def _start_text(game_no: int, opened_count: int = 0) -> str:
    remaining = PICKS_PER_GAME - opened_count

    return (
        "👻 <b>Где спрятался CASPER?</b>\n\n"
        "Соберите три одинаковых символа "
        "за пять открытий.\n\n"
        "👑 — VIP на 24 часа\n"
        "💜 — скидка 30% для диалога\n"
        f"⭐ — +{STAR_REWARD_AMOUNT} ⭐ "
        "на внутренний баланс\n"
        "👻 — CASPER может спугнуть удачу\n\n"
        f"Открыто: <b>{opened_count}/{PICKS_PER_GAME}</b>\n"
        f"Осталось: <b>{remaining}</b>\n"
        f"🎮 Игра: <b>{game_no}/{MAX_ATTEMPTS_PER_SEARCH}</b>"
    )


def _combination_text(symbols: list[str]) -> str:
    return " ".join(symbols)


async def _grant_final_reward(
    user_id: int,
    result: GameResult,
) -> tuple[GameResult, str]:
    combination = casper_rounds[user_id].symbols
    shown = _combination_text(combination)

    if result == "vip":
        if not await db.can_win_search_game_vip(user_id):
            return "draw", (
                "🤝 <b>Ничья!</b>\n\n"
                f"{shown}\n\n"
                "Награда уже недоступна для повторного выигрыша.\n\n"
                "Попробуйте ещё раз!"
            )

        await db.grant_search_game_vip(user_id)

        return "vip", (
            "🎉 <b>Победа!</b>\n\n"
            f"{shown}\n\n"
            "Вы собрали три короны!\n\n"
            "👑 VIP продлён на 24 часа."
        )

    if result == "discount":
        granted = await db.grant_search_game_discount(user_id)

        if not granted:
            return "draw", (
                "🤝 <b>Ничья!</b>\n\n"
                f"{shown}\n\n"
                "У вас уже сохранена скидка для диалога.\n\n"
                "Попробуйте ещё раз!"
            )

        return "discount", (
            "🎉 <b>Победа!</b>\n\n"
            f"{shown}\n\n"
            "Вы собрали три сердечка!\n\n"
            "💜 Скидка 30% активирована "
            "для диалога с вашим собеседником."
        )

    if result == "star":
        granted, stars_today = await db.grant_search_game_star(
            user_id,
            amount=STAR_REWARD_AMOUNT,
            daily_limit=STAR_DAILY_LIMIT,
        )

        if not granted:
            return "draw", (
                "🤝 <b>Ничья!</b>\n\n"
                f"{shown}\n\n"
                "Суточный лимит звёзд уже достигнут.\n\n"
                "Попробуйте ещё раз!"
            )

        balance = await db.get_user_balance(user_id)

        return "star", (
            "🎉 <b>Победа!</b>\n\n"
            f"{shown}\n\n"
            "Вы собрали три звезды!\n\n"
            f"⭐ +{STAR_REWARD_AMOUNT} ⭐ уже зачислены "
            "на ваш внутренний баланс.\n\n"
            f"Баланс: <b>{balance} ⭐</b>\n"
            f"Выиграно сегодня: "
            f"<b>{stars_today}/{STAR_DAILY_LIMIT} ⭐</b>"
        )

    if result == "casper":
        return "casper", (
            "👻 <b>CASPER оказался хитрее!</b>\n\n"
            f"{shown}\n\n"
            "CASPER спугнул вашу удачу...\n\n"
            "Попробуйте ещё раз!"
        )

    return "draw", (
        "🤝 <b>Ничья!</b>\n\n"
        f"{shown}\n\n"
        "Никому не удалось собрать "
        "три одинаковых символа.\n\n"
        "Попробуйте ещё раз!"
    )


async def delete_previous_casper_message(
    bot,
    user_id: int,
) -> None:
    message_id = casper_game_message_ids.pop(user_id, None)

    if not message_id:
        return

    try:
        await bot.delete_message(
            chat_id=user_id,
            message_id=message_id,
        )
    except Exception:
        pass


async def _send_new_board(
    *,
    bot,
    chat_id: int,
    user_id: int,
    game_no: int,
) -> None:
    result = await select_game_result(user_id, game_no)
    token = secrets.token_hex(5)

    round_data = CasperRound(
        token=token,
        user_id=user_id,
        message_id=0,
        game_no=game_no,
        planned_result=result,
        symbols=_build_symbols(result),
    )

    sent = await bot.send_message(
        chat_id=chat_id,
        text=_start_text(game_no),
        parse_mode="HTML",
        reply_markup=_board_keyboard(round_data),
    )

    round_data.message_id = sent.message_id
    casper_rounds[user_id] = round_data
    casper_game_message_ids[user_id] = sent.message_id


async def open_casper_board(
    message: Message,
    attempt_no: int,
) -> None:
    user_id = message.from_user.id

    await delete_previous_casper_message(
        message.bot,
        user_id,
    )

    await _send_new_board(
        bot=message.bot,
        chat_id=message.chat.id,
        user_id=user_id,
        game_no=attempt_no,
    )


@router.callback_query(F.data.startswith("casper_pick:"))
async def casper_pick_cell(callback: CallbackQuery):
    user_id = callback.from_user.id
    lock = casper_round_locks.setdefault(
        user_id,
        asyncio.Lock(),
    )

    async with lock:
        parts = callback.data.split(":")

        if len(parts) != 3:
            await callback.answer(
                "Игра недоступна.",
                show_alert=True,
            )
            return

        token = parts[1]

        try:
            selected_index = int(parts[2])
        except ValueError:
            await callback.answer(
                "Некорректная клетка.",
                show_alert=True,
            )
            return

        round_data = casper_rounds.get(user_id)

        if (
            not round_data
            or round_data.token != token
            or round_data.message_id != callback.message.message_id
        ):
            await callback.answer(
                "Эта игра уже неактивна.",
                show_alert=True,
            )
            return

        if round_data.finished:
            await callback.answer("Игра уже завершена.")
            return

        if selected_index in round_data.opened_cells:
            await callback.answer("Эта клетка уже открыта.")
            return

        symbol_index = len(round_data.opened_cells)
        round_data.opened_cells[selected_index] = (
            round_data.symbols[symbol_index]
        )

        if len(round_data.opened_cells) < PICKS_PER_GAME:
            await callback.message.edit_text(
                _start_text(
                    round_data.game_no,
                    len(round_data.opened_cells),
                ),
                parse_mode="HTML",
                reply_markup=_board_keyboard(round_data),
            )

            await callback.answer(
                f"Осталось открытий: "
                f"{PICKS_PER_GAME - len(round_data.opened_cells)}"
            )
            return

        round_data.finished = True

        final_result, result_text = await _grant_final_reward(
            user_id,
            round_data.planned_result,
        )
        round_data.planned_result = final_result

        await callback.message.edit_text(
            result_text,
            parse_mode="HTML",
            reply_markup=_board_keyboard(
                round_data,
                show_replay=True,
            ),
        )

        await callback.answer("Игра завершена")


@router.callback_query(F.data == "casper_play_again")
async def casper_play_again(callback: CallbackQuery):
    user_id = callback.from_user.id
    lock = casper_round_locks.setdefault(
        user_id,
        asyncio.Lock(),
    )

    async with lock:
        if await db.get_partner(user_id):
            await callback.answer(
                "Собеседник уже найден.",
                show_alert=True,
            )
            return

        if not await db.is_in_queue(user_id):
            await callback.answer(
                "Поиск собеседника уже завершён.",
                show_alert=True,
            )
            return

        games_played = search_game_attempts.get(user_id, 0)

        if games_played >= MAX_ATTEMPTS_PER_SEARCH:
            await callback.answer(
                "Все игры этого поиска уже использованы.",
                show_alert=True,
            )
            return

        games_played += 1
        search_game_attempts[user_id] = games_played

        try:
            await callback.message.delete()
        except Exception:
            pass

        casper_game_message_ids.pop(user_id, None)

        await _send_new_board(
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            user_id=user_id,
            game_no=games_played,
        )

        await callback.answer()


@router.callback_query(F.data == "casper_opened_cell")
async def casper_opened_cell(callback: CallbackQuery):
    await callback.answer("Эта клетка уже открыта.")


@router.callback_query(F.data == "casper_round_closed")
async def casper_round_closed(callback: CallbackQuery):
    await callback.answer("Игра уже завершена.")

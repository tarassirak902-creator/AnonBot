from __future__ import annotations

import random

GAME_NAMES = {
    "darts": "🎯 Дартс",
    "dice": "🎲 Кости",
    "basketball": "🏀 Баскетбол",
    "bowling": "🎳 Боулинг",
    "football": "⚽ Футбол",
    "slots": "🎰 Игровой автомат",
    "coin": "🪙 Орёл или решка",
    "rps": "✊ Камень, ножницы, бумага",
    "guess": "🔢 Угадай число",
}

TELEGRAM_DICE_EMOJIS = {
    "darts": "🎯",
    "dice": "🎲",
    "basketball": "🏀",
    "bowling": "🎳",
    "football": "⚽",
    "slots": "🎰",
}

CUSTOM_GAMES = {"coin", "rps", "guess"}


def solo_native_win(game_type: str, value: int, bet: int) -> int:
    if game_type == "darts":
        return bet * 3 if value == 6 else (int(bet * 1.5) if value in (4, 5) else 0)
    if game_type == "basketball":
        return bet * 3 if value in (4, 5) else 0
    if game_type == "bowling":
        return bet * 3 if value == 6 else (bet * 2 if value == 5 else 0)
    if game_type == "football":
        return bet * 3 if value in (4, 5) else 0
    if game_type == "slots":
        return bet * 5 if value == 64 else (bet * 2 if value in (1, 22, 43) else 0)
    return bet * 2 if value >= 5 else (bet if value == 4 else 0)


def play_custom_solo(game_type: str, bet: int) -> tuple[int, str]:
    if game_type == "coin":
        result = random.choice(("Орёл", "Решка"))
        win = bet * 2 if result == "Орёл" else 0
        return win, f"Монета: <b>{result}</b>. Вы играли за Орла."

    if game_type == "rps":
        options = ("Камень", "Ножницы", "Бумага")
        player = random.choice(options)
        bot = random.choice(options)
        wins = {("Камень", "Ножницы"), ("Ножницы", "Бумага"), ("Бумага", "Камень")}
        if player == bot:
            return bet, f"Вы: <b>{player}</b> · CASPER: <b>{bot}</b>. Ничья."
        if (player, bot) in wins:
            return bet * 2, f"Вы: <b>{player}</b> · CASPER: <b>{bot}</b>. Вы победили!"
        return 0, f"Вы: <b>{player}</b> · CASPER: <b>{bot}</b>. Победил CASPER."

    secret = random.randint(1, 5)
    guess = random.randint(1, 5)
    win = bet * 3 if guess == secret else 0
    return win, f"Ваше число: <b>{guess}</b> · Загаданное число: <b>{secret}</b>."


def play_custom_duel(game_type: str) -> tuple[int, int, str]:
    """Return comparison scores and a human-readable result.

    Greater score wins; equal scores are a draw.
    """
    if game_type == "coin":
        result = random.choice(("Орёл", "Решка"))
        return (1, 0, f"Выпал <b>{result}</b>. Первый игрок — Орёл, второй — Решка.") if result == "Орёл" else (0, 1, f"Выпал <b>{result}</b>. Первый игрок — Орёл, второй — Решка.")

    if game_type == "rps":
        options = ("Камень", "Ножницы", "Бумага")
        first = random.choice(options)
        second = random.choice(options)
        wins = {("Камень", "Ножницы"), ("Ножницы", "Бумага"), ("Бумага", "Камень")}
        if first == second:
            return 0, 0, f"Первый: <b>{first}</b> · Второй: <b>{second}</b>."
        return (1, 0, f"Первый: <b>{first}</b> · Второй: <b>{second}</b>.") if (first, second) in wins else (0, 1, f"Первый: <b>{first}</b> · Второй: <b>{second}</b>.")

    secret = random.randint(1, 10)
    first = random.randint(1, 10)
    second = random.randint(1, 10)
    distance_first = abs(secret - first)
    distance_second = abs(secret - second)
    text = f"Загадано: <b>{secret}</b> · Первый: <b>{first}</b> · Второй: <b>{second}</b>."
    if distance_first == distance_second:
        return 0, 0, text
    return (1, 0, text) if distance_first < distance_second else (0, 1, text)

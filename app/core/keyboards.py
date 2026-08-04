from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def _reply(rows, *, persistent: bool = True) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=persistent,
    )


def _inline(rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="🚀 Начать общение")],
        [KeyboardButton(text="❓ Анонимные вопросы"), KeyboardButton(text="🎮 Игры")],
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🎁 Пригласить друга")],
        [KeyboardButton(text="⚙️ Панель управления" if is_admin else "📣 Разместить рекламу")],
    ]
    return _reply(rows)


def main_menu_with_question(display_name: str, is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=f"❓ Написать {display_name} анонимно")],
        [KeyboardButton(text="🚀 Начать общение")],
        [KeyboardButton(text="❓ Анонимные вопросы"), KeyboardButton(text="🎮 Игры")],
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🎁 Пригласить друга")],
        [KeyboardButton(text="⚙️ Панель управления" if is_admin else "📣 Разместить рекламу")],
    ]
    return _reply(rows)


def chat_menu() -> ReplyKeyboardMarkup:
    return _reply([
        [KeyboardButton(text="🎁 Подарить подарок"), KeyboardButton(text="⭐ Кто собеседник")],
        [KeyboardButton(text="⚔️ Играть с собеседником"), KeyboardButton(text="⚠️ Пожаловаться")],
        [KeyboardButton(text="➡️ Следующий собеседник"), KeyboardButton(text="❌ Завершить диалог")],
    ])


def solo_games_menu_kb() -> InlineKeyboardMarkup:
    return _inline([
        [InlineKeyboardButton(text="🎯 Дартс", callback_data="game_solo_darts"), InlineKeyboardButton(text="🎲 Кости", callback_data="game_solo_dice")],
        [InlineKeyboardButton(text="🏀 Баскетбол", callback_data="game_solo_basketball"), InlineKeyboardButton(text="🎳 Боулинг", callback_data="game_solo_bowling")],
        [InlineKeyboardButton(text="⚽ Футбол", callback_data="game_solo_football"), InlineKeyboardButton(text="🎰 Автомат", callback_data="game_solo_slots")],
        [InlineKeyboardButton(text="🪙 Монетка", callback_data="game_solo_coin"), InlineKeyboardButton(text="✊ КНБ", callback_data="game_solo_rps")],
        [InlineKeyboardButton(text="🔢 Угадай число", callback_data="game_solo_guess")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="solo_games_close")],
    ])


def duel_games_menu_kb() -> InlineKeyboardMarkup:
    return _inline([
        [InlineKeyboardButton(text="🎯 Дартс", callback_data="game_duel_darts"), InlineKeyboardButton(text="🎲 Кости", callback_data="game_duel_dice")],
        [InlineKeyboardButton(text="🏀 Баскетбол", callback_data="game_duel_basketball"), InlineKeyboardButton(text="🎳 Боулинг", callback_data="game_duel_bowling")],
        [InlineKeyboardButton(text="⚽ Футбол", callback_data="game_duel_football"), InlineKeyboardButton(text="🎰 Автомат", callback_data="game_duel_slots")],
        [InlineKeyboardButton(text="🪙 Монетка", callback_data="game_duel_coin"), InlineKeyboardButton(text="✊ КНБ", callback_data="game_duel_rps")],
        [InlineKeyboardButton(text="🔢 Ближе к числу", callback_data="game_duel_guess")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="duel_games_close")],
    ])


def complaint_reasons() -> InlineKeyboardMarkup:
    return _inline([
        [InlineKeyboardButton(text="🔞 18+", callback_data="complaint_18"), InlineKeyboardButton(text="💰 Попрошайничество", callback_data="complaint_beg")],
        [InlineKeyboardButton(text="🎣 Скам", callback_data="complaint_scam"), InlineKeyboardButton(text="🚫 Спам", callback_data="complaint_spam")],
        [InlineKeyboardButton(text="🤬 Оскорбления", callback_data="complaint_insult"), InlineKeyboardButton(text="📌 Другое", callback_data="complaint_other")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="complaint_cancel")],
    ])


def admin_panel() -> ReplyKeyboardMarkup:
    return _reply([
        [KeyboardButton(text="📊 Статистика и пользователи"), KeyboardButton(text="📨 Рассылка")],
        [KeyboardButton(text="🎁 Управление подарками"), KeyboardButton(text="💸 Заявки на вывод")],
        [KeyboardButton(text="🚫 Запрещённые слова"), KeyboardButton(text="📢 Реклама")],
        [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="📋 Логи")],
        [KeyboardButton(text="↩️ Выход")],
    ])


def telegram_service_menu_kb() -> InlineKeyboardMarkup:
    return _inline([
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="service_refresh_bot"), InlineKeyboardButton(text="📖 О боте", callback_data="service_about")],
        [InlineKeyboardButton(text="🛟 Поддержка", url="https://t.me/dasha_pri"), InlineKeyboardButton(text="📢 Новости", url="https://t.me/caspergoapp")],
        [InlineKeyboardButton(text="🔐 Конфиденциальность", callback_data="service_privacy")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="service_menu_close")],
    ])


def service_about_kb() -> InlineKeyboardMarkup:
    return _inline([
        [InlineKeyboardButton(text="📢 Новости", url="https://t.me/caspergoapp"), InlineKeyboardButton(text="🛟 Поддержка", url="https://t.me/dasha_pri")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="service_menu_back")],
    ])


def service_privacy_kb() -> InlineKeyboardMarkup:
    return _inline([
        [InlineKeyboardButton(text="🛟 Поддержка", url="https://t.me/dasha_pri")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="service_menu_back")],
    ])


def question_target_menu(display_name: str = "") -> ReplyKeyboardMarkup:
    return _reply([
        [KeyboardButton(text="❓ Задать вопрос"), KeyboardButton(text="🎁 Подарок")],
        [KeyboardButton(text="🏠 Главное меню")],
    ])


def question_target_inline(display_name: str = "") -> InlineKeyboardMarkup:
    return _inline([
        [InlineKeyboardButton(text="❓ Задать вопрос", callback_data="questions:ask_target"), InlineKeyboardButton(text="🎁 Подарок", callback_data="questions:target_gift")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="nav_main_menu")],
    ])


def question_gift_inline() -> InlineKeyboardMarkup:
    return _inline([
        [InlineKeyboardButton(text="🎁 Подарок", callback_data="questions:gift_regular"), InlineKeyboardButton(text="⭐ Звёзды", callback_data="questions:gift_stars")],
        [InlineKeyboardButton(text="👑 VIP", callback_data="questions:gift_vip"), InlineKeyboardButton(text="💎 Premium", callback_data="questions:gift_premium")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="questions:gift_back")],
    ])


def question_gift_menu() -> ReplyKeyboardMarkup:
    return _reply([
        [KeyboardButton(text="🎁 Подарок"), KeyboardButton(text="⭐ Звёзды")],
        [KeyboardButton(text="👑 VIP статус"), KeyboardButton(text="💎 Telegram Premium")],
        [KeyboardButton(text="⬅️ Назад")],
    ])


def question_custom_stars_menu() -> ReplyKeyboardMarkup:
    return _reply([[KeyboardButton(text="⬅️ Назад")]])


def question_writing_menu() -> ReplyKeyboardMarkup:
    return _reply([[KeyboardButton(text="⬅️ Назад")]])


def question_back_menu() -> ReplyKeyboardMarkup:
    return _reply([[KeyboardButton(text="⬅️ Назад")]])


def questions_home_menu() -> ReplyKeyboardMarkup:
    return _reply([
        [KeyboardButton(text="📥 Мои вопросы"), KeyboardButton(text="🔗 Моя ссылка")],
        [KeyboardButton(text="💬 Ответы на мои вопросы"), KeyboardButton(text="🏠 Главное меню")],
    ])


def questions_list_navigation(has_prev: bool, has_next: bool) -> ReplyKeyboardMarkup:
    navigation_row = []
    if has_prev:
        navigation_row.append(KeyboardButton(text="⬅️ Предыдущие вопросы"))
    if has_next:
        navigation_row.append(KeyboardButton(text="Следующие вопросы ➡️"))
    rows = [navigation_row] if navigation_row else []
    rows.append([KeyboardButton(text="↩️ Назад к разделу вопросов"), KeyboardButton(text="🏠 Главное меню")])
    return _reply(rows)


def answers_list_navigation(has_prev: bool, has_next: bool) -> ReplyKeyboardMarkup:
    navigation_row = []
    if has_prev:
        navigation_row.append(KeyboardButton(text="⬅️ Предыдущие ответы"))
    if has_next:
        navigation_row.append(KeyboardButton(text="Следующие ответы ➡️"))
    rows = [navigation_row] if navigation_row else []
    rows.append([KeyboardButton(text="↩️ Назад к разделу вопросов"), KeyboardButton(text="🏠 Главное меню")])
    return _reply(rows)


def question_card_menu(author_revealed: bool = False) -> ReplyKeyboardMarkup:
    author_button = "👤 Посмотреть автора" if author_revealed else "👤 Узнать автора — 100 ⭐"
    return _reply([
        [KeyboardButton(text="💬 Ответить"), KeyboardButton(text=author_button)],
        [KeyboardButton(text="🎁 Подарок"), KeyboardButton(text="↩️ Назад к вопросам")],
        [KeyboardButton(text="🏠 Главное меню")],
    ])


def question_answer_menu() -> ReplyKeyboardMarkup:
    return _reply([
        [KeyboardButton(text="❓ Задать ещё вопрос"), KeyboardButton(text="🎁 Подарок")],
        [KeyboardButton(text="↩️ Назад к ответам"), KeyboardButton(text="🏠 Главное меню")],
    ])


def question_link_menu() -> ReplyKeyboardMarkup:
    return _reply([
        [KeyboardButton(text="📖 Как установить в профиль")],
        [KeyboardButton(text="⬅️ Назад")],
    ])


def question_profile_help_menu() -> ReplyKeyboardMarkup:
    return _reply([[KeyboardButton(text="⬅️ Назад к ссылке")]])


def answer_writing_menu() -> ReplyKeyboardMarkup:
    return _reply([
        [KeyboardButton(text="↩️ Назад к вопросу"), KeyboardButton(text="🏠 Главное меню")],
    ])


def questions_home_inline() -> InlineKeyboardMarkup:
    return _inline([
        [InlineKeyboardButton(text="📥 Вопросы", callback_data="questions:mine"), InlineKeyboardButton(text="💬 Ответы", callback_data="questions:answers")],
        [InlineKeyboardButton(text="🔗 Моя ссылка", callback_data="questions:link")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="nav_main_menu")],
    ])


def questions_page_inline(rows, has_prev: bool, has_next: bool, offset: int) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=f"❓ Вопрос №{row[0]}", callback_data=f"questions:view:{row[1]}")] for row in rows]
    nav = []
    if has_prev:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"questions:page:{max(0, offset-5)}"))
    if has_next:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"questions:page:{offset+5}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="questions:home")])
    return _inline(buttons)


def answers_page_inline(rows, has_prev: bool, has_next: bool, offset: int) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=f"💬 Ответ №{row[0]}", callback_data=f"questions:answer_view:{row[1]}")] for row in rows]
    nav = []
    if has_prev:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"questions:answers_page:{max(0, offset-5)}"))
    if has_next:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"questions:answers_page:{offset+5}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="questions:home")])
    return _inline(buttons)


def question_link_inline() -> InlineKeyboardMarkup:
    return _inline([
        [InlineKeyboardButton(text="📖 Как добавить в профиль", callback_data="questions:profile_help")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="questions:home")],
    ])


def question_profile_help_inline() -> InlineKeyboardMarkup:
    return _inline([[InlineKeyboardButton(text="⬅️ К ссылке", callback_data="questions:link")]])


def question_card_inline(author_revealed: bool = False) -> InlineKeyboardMarkup:
    author_text = "👤 Автор" if author_revealed else "👤 Автор — 100 ⭐"
    author_cb = "questions:show_author" if author_revealed else "questions:buy_reveal"
    return _inline([
        [InlineKeyboardButton(text="💬 Ответить", callback_data="questions:reply"), InlineKeyboardButton(text="🎁 Подарок", callback_data="questions:gift")],
        [InlineKeyboardButton(text=author_text, callback_data=author_cb)],
        [InlineKeyboardButton(text="⬅️ К вопросам", callback_data="questions:back_mine")],
    ])


def answer_card_inline() -> InlineKeyboardMarkup:
    return _inline([
        [InlineKeyboardButton(text="❓ Ещё вопрос", callback_data="questions:ask_again"), InlineKeyboardButton(text="🎁 Подарок", callback_data="questions:answer_gift")],
        [InlineKeyboardButton(text="⬅️ К ответам", callback_data="questions:back_answers")],
    ])


def inline_back(callback_data: str, text: str = "⬅️ Назад") -> InlineKeyboardMarkup:
    return _inline([[InlineKeyboardButton(text=text, callback_data=callback_data)]])

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Главное меню вне диалога"""
    keyboard = [
        [KeyboardButton(text="💬 Найти собеседника")],
        [KeyboardButton(text="🎮 Мини-игры"), KeyboardButton(text="❓ Вопросы")],
        [KeyboardButton(text="👤 Моя анкета"), KeyboardButton(text="👥 Пригласить друга")],
    ]
    if is_admin:
        keyboard.append([KeyboardButton(text="⚙️ Админ-панель CASPER")])
    else:
        keyboard.append([KeyboardButton(text="📢 Реклама в CASPER")])
    
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=True,
    )


def main_menu_with_question(display_name: str, is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Главное меню после start=ask_: персональная кнопка первым рядом."""
    keyboard = [
        [KeyboardButton(text=f"❓ Задать анонимный вопрос {display_name}")],
        [KeyboardButton(text="💬 Найти собеседника")],
        [KeyboardButton(text="🎮 Мини-игры"), KeyboardButton(text="❓ Вопросы")],
        [KeyboardButton(text="👤 Моя анкета"), KeyboardButton(text="👥 Пригласить друга")],
    ]
    if is_admin:
        keyboard.append([KeyboardButton(text="⚙️ Админ-панель CASPER")])
    else:
        keyboard.append([KeyboardButton(text="📢 Реклама в CASPER")])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=True,
    )

def chat_menu() -> ReplyKeyboardMarkup:
    """Меню управления во время активного диалога"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎁 Подарить подарок"), KeyboardButton(text="⭐ Кто собеседник")],
            [KeyboardButton(text="⚔️ Играть с собеседником"), KeyboardButton(text="⚠️ Пожаловаться")],
            [KeyboardButton(text="➡️ Следующий собеседник"), KeyboardButton(text="❌ Завершить диалог")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=True,
    )

def solo_games_menu_kb() -> InlineKeyboardMarkup:
    """Инлайн-меню игр против CASPER."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎯 Дартс", callback_data="game_solo_darts"), InlineKeyboardButton(text="🎲 Кости", callback_data="game_solo_dice")],
            [InlineKeyboardButton(text="🏀 Баскетбол", callback_data="game_solo_basketball"), InlineKeyboardButton(text="🎳 Боулинг", callback_data="game_solo_bowling")],
            [InlineKeyboardButton(text="⚽ Футбол", callback_data="game_solo_football"), InlineKeyboardButton(text="🎰 Автомат", callback_data="game_solo_slots")],
            [InlineKeyboardButton(text="🪙 Орёл или решка", callback_data="game_solo_coin")],
            [InlineKeyboardButton(text="✊ Камень, ножницы, бумага", callback_data="game_solo_rps")],
            [InlineKeyboardButton(text="🔢 Угадай число", callback_data="game_solo_guess")],
            [InlineKeyboardButton(text="↩️ Назад", callback_data="solo_games_close")],
        ]
    )


def duel_games_menu_kb() -> InlineKeyboardMarkup:
    """Инлайн-меню дуэлей с собеседником."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎯 Дартс", callback_data="game_duel_darts"), InlineKeyboardButton(text="🎲 Кости", callback_data="game_duel_dice")],
            [InlineKeyboardButton(text="🏀 Баскетбол", callback_data="game_duel_basketball"), InlineKeyboardButton(text="🎳 Боулинг", callback_data="game_duel_bowling")],
            [InlineKeyboardButton(text="⚽ Футбол", callback_data="game_duel_football"), InlineKeyboardButton(text="🎰 Автомат", callback_data="game_duel_slots")],
            [InlineKeyboardButton(text="🪙 Орёл или решка", callback_data="game_duel_coin")],
            [InlineKeyboardButton(text="✊ Камень, ножницы, бумага", callback_data="game_duel_rps")],
            [InlineKeyboardButton(text="🔢 Кто ближе к числу", callback_data="game_duel_guess")],
            [InlineKeyboardButton(text="↩️ Назад", callback_data="duel_games_close")],
        ]
    )

def complaint_reasons() -> InlineKeyboardMarkup:
    """Инлайн-меню выбора причины жалобы"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔞 Контент 18+", callback_data="complaint_18"),
                InlineKeyboardButton(text="💰 Попрошайничество", callback_data="complaint_beg")
            ],
            [
                InlineKeyboardButton(text="🎣 Скам", callback_data="complaint_scam"),
                InlineKeyboardButton(text="🚫 Спам", callback_data="complaint_spam")
            ],
            [
                InlineKeyboardButton(text="🤬 Оскорбления", callback_data="complaint_insult"),
                InlineKeyboardButton(text="📌 Другое", callback_data="complaint_other")
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="complaint_cancel")
            ]
        ]
    )

def admin_panel() -> ReplyKeyboardMarkup:
    """Нижнее меню используется только на главном экране админ-панели."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Статистика и пользователи"), KeyboardButton(text="📨 Рассылка")],
            [KeyboardButton(text="🚫 Запрещённые слова"), KeyboardButton(text="🎁 Управление подарками")],
            [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="📋 Логи")],
            [KeyboardButton(text="💸 Заявки на вывод"), KeyboardButton(text="📢 Реклама")],
            [KeyboardButton(text="↩️ Выход")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=True,
    )


def telegram_service_menu_kb() -> InlineKeyboardMarkup:
    """Сервисное меню, открываемое через синюю кнопку Telegram «Меню»."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить бота", callback_data="service_refresh_bot")],
            [InlineKeyboardButton(text="🛟 Техническая поддержка", url="https://t.me/dasha_pri")],
            [InlineKeyboardButton(text="📢 Новости и обновления", url="https://t.me/caspergoapp")],
            [InlineKeyboardButton(text="📖 О боте", callback_data="service_about")],
            [InlineKeyboardButton(text="🔐 Политика конфиденциальности", callback_data="service_privacy")],
            [InlineKeyboardButton(text="❌ Закрыть меню", callback_data="service_menu_close")],
        ]
    )


def service_about_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Новости", url="https://t.me/caspergoapp")],
            [InlineKeyboardButton(text="🛟 Поддержка", url="https://t.me/dasha_pri")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="service_menu_back")],
        ]
    )


def service_privacy_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛟 Поддержка", url="https://t.me/dasha_pri")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="service_menu_back")],
        ]
    )


def question_target_menu(display_name: str = "") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❓ Задать вопрос")],
            [KeyboardButton(text="🎁 Подарок")],
            [KeyboardButton(text="🏠 Главное меню")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=True,
    )


def question_target_inline(display_name: str = "") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❓ Задать вопрос", callback_data="questions:ask_target")],
        [InlineKeyboardButton(text="🎁 Подарок", callback_data="questions:target_gift")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="nav_main_menu")],
    ])


def question_gift_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Подарок", callback_data="questions:gift_regular"),
         InlineKeyboardButton(text="⭐ Звёзды", callback_data="questions:gift_stars")],
        [InlineKeyboardButton(text="👑 VIP статус", callback_data="questions:gift_vip"),
         InlineKeyboardButton(text="💎 Telegram Premium", callback_data="questions:gift_premium")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="questions:gift_back")],
    ])

def question_gift_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎁 Подарок"), KeyboardButton(text="⭐ Звёзды")],
            [KeyboardButton(text="👑 VIP статус"), KeyboardButton(text="💎 Telegram Premium")],
            [KeyboardButton(text="⬅️ Назад")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=True,
    )


def question_custom_stars_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ Назад")]],
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=True,
    )


def question_writing_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ Назад")]],
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=True,
    )


def question_back_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ Назад")]],
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=True,
    )


def questions_home_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📥 Мои вопросы"), KeyboardButton(text="🔗 Моя ссылка")],
            [KeyboardButton(text="💬 Ответы на мои вопросы")],
            [KeyboardButton(text="🏠 Главное меню")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=True,
    )


def questions_list_navigation(has_prev: bool, has_next: bool) -> ReplyKeyboardMarkup:
    navigation_row = []
    if has_prev:
        navigation_row.append(KeyboardButton(text="⬅️ Предыдущие вопросы"))
    if has_next:
        navigation_row.append(KeyboardButton(text="Следующие вопросы ➡️"))
    keyboard = []
    if navigation_row:
        keyboard.append(navigation_row)
    keyboard.extend([
        [KeyboardButton(text="↩️ Назад к разделу вопросов")],
        [KeyboardButton(text="🏠 Главное меню")],
    ])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def answers_list_navigation(has_prev: bool, has_next: bool) -> ReplyKeyboardMarkup:
    navigation_row = []
    if has_prev:
        navigation_row.append(KeyboardButton(text="⬅️ Предыдущие ответы"))
    if has_next:
        navigation_row.append(KeyboardButton(text="Следующие ответы ➡️"))
    keyboard = []
    if navigation_row:
        keyboard.append(navigation_row)
    keyboard.extend([
        [KeyboardButton(text="↩️ Назад к разделу вопросов")],
        [KeyboardButton(text="🏠 Главное меню")],
    ])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def question_card_menu(author_revealed: bool = False) -> ReplyKeyboardMarkup:
    author_button = "👤 Посмотреть автора" if author_revealed else "👤 Узнать автора — 100 ⭐"
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💬 Ответить"), KeyboardButton(text=author_button)],
            [KeyboardButton(text="🎁 Подарок")],
            [KeyboardButton(text="↩️ Назад к вопросам")],
            [KeyboardButton(text="🏠 Главное меню")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=True,
    )


def question_answer_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❓ Задать ещё вопрос")],
            [KeyboardButton(text="🎁 Подарок")],
            [KeyboardButton(text="↩️ Назад к ответам")],
            [KeyboardButton(text="🏠 Главное меню")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=True,
    )


def question_link_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📖 Как установить в профиль")],
            [KeyboardButton(text="⬅️ Назад")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=True,
    )


def question_profile_help_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ Назад к ссылке")]],
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=True,
    )


def answer_writing_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="↩️ Назад к вопросу")],
            [KeyboardButton(text="🏠 Главное меню")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        is_persistent=True,
    )


# ===== Inline-навигация раздела анонимных вопросов =====
def questions_home_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Мои вопросы", callback_data="questions:mine"), InlineKeyboardButton(text="🔗 Моя ссылка", callback_data="questions:link")],
        [InlineKeyboardButton(text="💬 Ответы на мои вопросы", callback_data="questions:answers")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="nav_main_menu")],
    ])

def questions_page_inline(rows, has_prev: bool, has_next: bool, offset: int) -> InlineKeyboardMarkup:
    buttons=[]
    if rows:
        for row in rows:
            qid=row[0]
            created=row[7] if len(row)>7 else ""
            label=f"❓ Вопрос №{qid}"
            buttons.append([InlineKeyboardButton(text=label, callback_data=f"questions:view:{row[1]}")])
    nav=[]
    if has_prev: nav.append(InlineKeyboardButton(text="⬅️ Предыдущие", callback_data=f"questions:page:{max(0, offset-5)}"))
    if has_next: nav.append(InlineKeyboardButton(text="Следующие ➡️", callback_data=f"questions:page:{offset+5}"))
    if nav: buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="questions:home")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def answers_page_inline(rows, has_prev: bool, has_next: bool, offset: int) -> InlineKeyboardMarkup:
    buttons=[]
    if rows:
        for row in rows:
            buttons.append([InlineKeyboardButton(text=f"💬 Ответ №{row[0]}", callback_data=f"questions:answer_view:{row[1]}")])
    nav=[]
    if has_prev: nav.append(InlineKeyboardButton(text="⬅️ Предыдущие", callback_data=f"questions:answers_page:{max(0, offset-5)}"))
    if has_next: nav.append(InlineKeyboardButton(text="Следующие ➡️", callback_data=f"questions:answers_page:{offset+5}"))
    if nav: buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="questions:home")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def question_link_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Как установить в профиль", callback_data="questions:profile_help")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="questions:home")],
    ])

def question_profile_help_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад к ссылке", callback_data="questions:link")]])

def question_card_inline(author_revealed: bool=False) -> InlineKeyboardMarkup:
    author_text="👤 Посмотреть автора" if author_revealed else "👤 Узнать автора — 100 ⭐"
    author_cb="questions:show_author" if author_revealed else "questions:buy_reveal"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Ответить", callback_data="questions:reply")],
        [InlineKeyboardButton(text=author_text, callback_data=author_cb)],
        [InlineKeyboardButton(text="🎁 Подарок", callback_data="questions:gift")],
        [InlineKeyboardButton(text="⬅️ Назад к вопросам", callback_data="questions:back_mine")],
    ])

def answer_card_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❓ Задать ещё вопрос", callback_data="questions:ask_again")],
        [InlineKeyboardButton(text="🎁 Подарок", callback_data="questions:answer_gift")],
        [InlineKeyboardButton(text="⬅️ Назад к ответам", callback_data="questions:back_answers")],
    ])

def inline_back(callback_data: str, text: str="⬅️ Назад") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=callback_data)]])

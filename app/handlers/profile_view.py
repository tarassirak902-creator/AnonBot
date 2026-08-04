from .shared import *


def get_profile_keyboard(is_vip: bool) -> InlineKeyboardMarkup:
    vip_btn_text = "👑 VIP подписка активна (100 ⭐ / мес)" if is_vip else "👑 Купить VIP подписку (100 ⭐ / мес)"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=vip_btn_text, callback_data="buy_vip_sub")],
        [InlineKeyboardButton(text="💸 Вывести звёзды", callback_data="profile_withdraw")],
        [
            InlineKeyboardButton(text="🎀 История подарков", callback_data="profile_my_received_gifts"),
            InlineKeyboardButton(text="🎁 Отправленные подарки", callback_data="profile_my_sent_gifts"),
        ],
        [InlineKeyboardButton(text="🔍 Раскрытые собеседники", callback_data="profile_my_revealed")],
        [InlineKeyboardButton(text="👥 Приглашённые пользователи", callback_data="profile_invited_users")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="profile_refresh")],
        [InlineKeyboardButton(text="↩️ Назад в главное меню", callback_data="nav_main_menu")],
    ])


async def build_profile_screen(user_id: int) -> tuple[str, InlineKeyboardMarkup] | None:
    """Единственный шаблон анкеты для открытия, обновления и возврата назад."""
    user = await db.get_user(user_id)
    if not user:
        return None

    joined_str = user[4] if len(user) > 4 and user[4] else None
    joined_date = datetime.fromisoformat(joined_str) if joined_str else datetime.now()
    days = max(0, (datetime.now() - joined_date).days)
    warnings_count = user[6] if len(user) > 6 else 0
    complaints = user[9] if len(user) > 9 else 0
    stars_balance = await db.get_user_balance(user_id)
    is_vip = await db.is_user_vip(user_id)
    vip_status = "Активен ✨ (Скидка 30% на подарки)" if is_vip else "Отсутствует"

    received_summary = await db.get_user_received_gifts_summary(user_id)
    if received_summary:
        gifts_list = [f"{emoji} {name} <b>(x{count})</b>" for emoji, name, count in received_summary]
        gifts_text = "• " + "\n• ".join(gifts_list)
    else:
        gifts_text = "<i>Пока нет полученных подарков</i>"

    text = (
        "👤 <b>Моя анкета в CASPER</b>\n"
        f"📅 <b>Вы с нами уже:</b> {days} дн.\n"
        f"👑 <b>VIP статус:</b> {vip_status}\n"
        f"⭐ <b>Ваш баланс звёзд:</b> <b>{stars_balance} ⭐</b>\n"
        f"⚠️ <b>Отправлено жалоб на собеседника:</b> {complaints}\n"
        f"🚨 <b>Получено предупреждений от администрации:</b> {warnings_count}/3\n\n"
        "🎀 <b>Получено подарков от собеседников:</b>\n"
        f"{gifts_text}\n"
    )
    return text, get_profile_keyboard(is_vip)


async def send_profile_screen(message: Message, user_id: int):
    screen = await build_profile_screen(user_id)
    if screen is None:
        return None
    text, keyboard = screen
    return await send_brand_card(message, "profile", text, keyboard)

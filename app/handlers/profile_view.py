from .shared import *
from app.services.profile_insights import (
    achievement_progress,
    build_achievements,
    load_profile_insights,
)


def get_profile_keyboard(is_vip: bool) -> InlineKeyboardMarkup:
    vip_btn_text = "👑 VIP подписка активна (100 ⭐ / мес)" if is_vip else "👑 Купить VIP подписку (100 ⭐ / мес)"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏆 Мои достижения", callback_data="profile_achievements")],
        [InlineKeyboardButton(text=vip_btn_text, callback_data="buy_vip_sub")],
        [InlineKeyboardButton(text="💸 Вывести звёзды", callback_data="profile_withdraw")],
        [
            InlineKeyboardButton(text="🎀 Полученные подарки", callback_data="profile_my_received_gifts"),
            InlineKeyboardButton(text="🎁 Отправленные подарки", callback_data="profile_my_sent_gifts"),
        ],
        [InlineKeyboardButton(text="🔍 Раскрытые собеседники", callback_data="profile_my_revealed")],
        [InlineKeyboardButton(text="👥 Приглашённые пользователи", callback_data="profile_invited_users")],
        [InlineKeyboardButton(text="🔄 Обновить статистику", callback_data="profile_refresh")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="nav_main_menu")],
    ])


async def build_profile_screen(user_id: int) -> tuple[str, InlineKeyboardMarkup] | None:
    """Build the canonical profile screen with live activity counters."""
    user = await db.get_user(user_id)
    if not user:
        return None

    joined_str = user[4] if len(user) > 4 and user[4] else None
    warnings_count = int(user[6] if len(user) > 6 else 0)
    complaints = int(user[9] if len(user) > 9 else 0)
    stars_balance = await db.get_user_balance(user_id)
    is_vip = await db.is_user_vip(user_id)
    insights = await load_profile_insights(user_id, joined_str)
    achievements = build_achievements(insights, is_vip=is_vip, stars_balance=stars_balance)
    unlocked, total = achievement_progress(achievements)
    vip_status = "Активен ✨" if is_vip else "Не активирован"

    text = (
        "👤 <b>Профиль CASPER</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"📅 В боте: <b>{insights.days_in_bot} дн.</b>\n"
        f"👑 VIP: <b>{vip_status}</b>\n"
        f"⭐ Баланс: <b>{stars_balance} ⭐</b>\n"
        f"🏆 Достижения: <b>{unlocked}/{total}</b>\n\n"
        "📊 <b>Активность</b>\n"
        f"❓ Отправлено вопросов: <b>{insights.questions_sent}</b>\n"
        f"📥 Получено вопросов: <b>{insights.questions_received}</b>\n"
        f"💬 Дано ответов: <b>{insights.questions_answered}</b>\n"
        f"✅ Получено ответов: <b>{insights.answers_received}</b>\n"
        f"🔗 Переходов по ссылке: <b>{insights.link_visits}</b>\n"
        f"🎁 Подарков отправлено: <b>{insights.gifts_sent}</b>\n"
        f"🎀 Подарков получено: <b>{insights.gifts_received}</b>\n\n"
        "🛡 <b>Безопасность</b>\n"
        f"⚠️ Жалоб отправлено: <b>{complaints}</b>\n"
        f"🚨 Предупреждений: <b>{warnings_count}/3</b>"
    )
    return text, get_profile_keyboard(is_vip)


async def send_profile_screen(message: Message, user_id: int):
    screen = await build_profile_screen(user_id)
    if screen is None:
        return None
    text, keyboard = screen
    return await send_brand_card(message, "profile", text, keyboard)

from .shared import *
from app.core.ui_copy import metric, screen, section
from app.services.profile_insights import (
    achievement_progress,
    build_achievements,
    load_profile_insights,
)


def get_profile_keyboard(is_vip: bool) -> InlineKeyboardMarkup:
    vip_btn_text = "👑 VIP активен" if is_vip else "👑 Купить VIP"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏆 Достижения", callback_data="profile_achievements"),
            InlineKeyboardButton(text="🔄 Обновить", callback_data="profile_refresh"),
        ],
        [
            InlineKeyboardButton(text=vip_btn_text, callback_data="buy_vip_sub"),
            InlineKeyboardButton(text="💸 Вывод", callback_data="profile_withdraw"),
        ],
        [
            InlineKeyboardButton(text="🎀 Полученные", callback_data="profile_my_received_gifts"),
            InlineKeyboardButton(text="🎁 Отправленные", callback_data="profile_my_sent_gifts"),
        ],
        [
            InlineKeyboardButton(text="🔍 Раскрытия", callback_data="profile_my_revealed"),
            InlineKeyboardButton(text="👥 Приглашения", callback_data="profile_invited_users"),
        ],
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

    text = screen(
        "👤 Профиль",
        sections=(
            section("Статус", (
                metric("📅", "В боте", f"{insights.days_in_bot} дн."),
                metric("👑", "VIP", "активен" if is_vip else "не активирован"),
                metric("⭐", "Баланс", f"{stars_balance} ⭐"),
                metric("🏆", "Достижения", f"{unlocked}/{total}"),
            )),
            section("Активность", (
                metric("❓", "Вопросов отправлено", insights.questions_sent),
                metric("📥", "Вопросов получено", insights.questions_received),
                metric("💬", "Ответов дано", insights.questions_answered),
                metric("✅", "Ответов получено", insights.answers_received),
                metric("🔗", "Переходов по ссылке", insights.link_visits),
                metric("🎁", "Подарков отправлено", insights.gifts_sent),
                metric("🎀", "Подарков получено", insights.gifts_received),
            )),
            section("Безопасность", (
                metric("⚠️", "Жалоб отправлено", complaints),
                metric("🚨", "Предупреждений", f"{warnings_count}/3"),
            )),
        ),
        footer="Выберите действие ниже.",
    )
    return text, get_profile_keyboard(is_vip)


async def send_profile_screen(message: Message, user_id: int):
    profile_screen = await build_profile_screen(user_id)
    if profile_screen is None:
        return None
    text, keyboard = profile_screen
    return await send_brand_card(message, "profile", text, keyboard)

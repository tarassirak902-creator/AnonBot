from .shared import *
from app.core.ui_copy import metric, screen, section
from app.services.profile_insights import (
    achievement_progress,
    build_achievements,
    load_profile_insights,
)


PROFILE_TITLE = "👤 Мой профиль"


def get_profile_keyboard(is_vip: bool) -> InlineKeyboardMarkup:
    vip_btn_text = "👑 Управление VIP" if is_vip else "👑 Подключить VIP"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Забрать бонус", callback_data="profile_daily_reward")],
        [InlineKeyboardButton(text="🏆 Мои достижения", callback_data="profile_achievements")],
        [
            InlineKeyboardButton(text="⭐ Баланс", callback_data="profile_withdraw"),
            InlineKeyboardButton(text=vip_btn_text, callback_data="buy_vip_sub"),
        ],
        [
            InlineKeyboardButton(text="🎁 Подарки", callback_data="profile_my_received_gifts"),
            InlineKeyboardButton(text="👥 Друзья", callback_data="profile_invited_users"),
        ],
        [
            InlineKeyboardButton(text="🔍 Раскрытия", callback_data="profile_my_revealed"),
            InlineKeyboardButton(text="🔄 Обновить", callback_data="profile_refresh"),
        ],
        [InlineKeyboardButton(text="🏠 Главная", callback_data="nav_main_menu")],
    ])


async def build_profile_screen(user_id: int) -> tuple[str, InlineKeyboardMarkup] | None:
    user = await db.get_user(user_id)
    if not user:
        return None

    username = user[1] if len(user) > 1 and user[1] else None
    first_name = user[2] if len(user) > 2 and user[2] else "Пользователь"
    joined_str = user[4] if len(user) > 4 and user[4] else None
    warnings_count = int(user[6] if len(user) > 6 else 0)
    complaints = int(user[9] if len(user) > 9 else 0)
    stars_balance = await db.get_user_balance(user_id)
    is_vip = await db.is_user_vip(user_id)
    insights = await load_profile_insights(user_id, joined_str)
    achievements = build_achievements(insights, is_vip=is_vip, stars_balance=stars_balance)
    unlocked, total = achievement_progress(achievements)
    reputation = await db.get_reputation(user_id)

    identity = first_name
    if username:
        identity += f" · @{username}"

    status_line = "👑 VIP" if is_vip else "🌙 Обычный"
    rating_text = f"{reputation['score']:+.1f}%" if reputation['total'] else "нет оценок"
    text = screen(
        PROFILE_TITLE,
        intro=(
            f"<b>{identity}</b>\n"
            f"{status_line} · ⭐ <b>{stars_balance}</b> · 🏆 <b>{unlocked}/{total}</b>"
        ),
        sections=(
            section("Прогресс", (
                metric("⚡", "Уровень", reputation["level"]),
                metric("✨", "XP", reputation["xp"]),
                metric("⭐", "Репутация", rating_text),
                metric("🗳", "Оценок", reputation["total"]),
            )),
            section("Активность", (
                metric("💬", "Диалогов", insights.completed_chats),
                metric("📅", "Дней с CASPER", insights.days_in_bot),
                metric("🎁", "Подарков", insights.gifts_received),
                metric("👥", "Друзей", insights.referrals_total),
            )),
            section("Вопросы", (
                metric("📥", "Получено", insights.questions_received),
                metric("✉️", "Отправлено", insights.questions_sent),
                metric("✅", "Ответов", insights.answers_received),
                metric("💬", "Ответил", insights.questions_answered),
            )),
            section("Безопасность", (
                metric("⚠️", "Жалоб", complaints),
                metric("🚨", "Предупреждений", f"{warnings_count}/3"),
            )),
        ),
        footer="Ежедневный бонус повышает XP и серию входов.",
    )
    return text, get_profile_keyboard(is_vip)


async def send_profile_screen(message: Message, user_id: int):
    profile_screen = await build_profile_screen(user_id)
    if profile_screen is None:
        return None
    text, keyboard = profile_screen
    return await send_brand_card(message, "profile", text, keyboard)

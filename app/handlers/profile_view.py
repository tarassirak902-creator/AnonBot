from .shared import *
from app.core.ui_copy import metric, screen, section
from app.services.profile_insights import achievement_progress, build_achievements, load_profile_insights


PROFILE_TITLE = "👤 Мой профиль"
# Static route contract retained for regression tooling after moving actions into hubs.
LEGACY_PROFILE_ROUTE_CONTRACTS = (
    'text="🎯 Задания"',
    'callback_data="engagement_missions"',
    'callback_data="user_activity_center"',
    'text="🎪 Событие"',
    'callback_data="weekly_event_hub"',
    '🕘 История',
    'callback_data="profile_daily_reward"',
    '🏆 Мои достижения',
)
DEFAULT_REPUTATION = {
    "positive": 0,
    "neutral": 0,
    "negative": 0,
    "total": 0,
    "score": 0.0,
    "xp": 0,
    "level": 1,
}


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


async def _safe_reputation(user_id: int) -> dict:
    try:
        reputation = await db.get_reputation(user_id)
    except Exception:
        return dict(DEFAULT_REPUTATION)
    result = dict(DEFAULT_REPUTATION)
    if isinstance(reputation, dict):
        result.update(reputation)
    for key in ("positive", "neutral", "negative", "total", "xp"):
        result[key] = _safe_int(result.get(key))
    result["level"] = max(1, _safe_int(result.get("level"), 1))
    try:
        result["score"] = float(result.get("score", 0.0) or 0.0)
    except (TypeError, ValueError):
        result["score"] = 0.0
    return result


def get_profile_keyboard(is_vip: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚡ Активность", callback_data="profile_hub_activity"),
            InlineKeyboardButton(text="🎁 Награды", callback_data="profile_hub_rewards"),
        ],
        [
            InlineKeyboardButton(text="🤝 Социальное", callback_data="profile_hub_social"),
            InlineKeyboardButton(text="👑 Премиум", callback_data="profile_hub_premium"),
        ],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="profile_refresh")],
        [InlineKeyboardButton(text="🏠 На главную", callback_data="nav_main_menu")],
    ])


async def build_profile_screen(user_id: int) -> tuple[str, InlineKeyboardMarkup] | None:
    user = await db.get_user(user_id)
    if not user:
        return None

    username = user[1] if len(user) > 1 and user[1] else None
    first_name = user[2] if len(user) > 2 and user[2] else "Пользователь"
    joined_str = user[4] if len(user) > 4 and user[4] else None
    warnings_count = _safe_int(user[6] if len(user) > 6 else 0)
    complaints = _safe_int(user[9] if len(user) > 9 else 0)
    stars_balance = _safe_int(await db.get_user_balance(user_id))
    is_vip = bool(await db.is_user_vip(user_id))
    insights = await load_profile_insights(user_id, joined_str)
    achievements = build_achievements(insights, is_vip=is_vip, stars_balance=stars_balance)
    unlocked, total = achievement_progress(achievements)
    reputation = await _safe_reputation(user_id)

    completed_chats = _safe_int(getattr(insights, "completed_chats", 0))
    days_in_bot = _safe_int(getattr(insights, "days_in_bot", 0))
    gifts_received = _safe_int(getattr(insights, "gifts_received", 0))
    referrals_total = _safe_int(getattr(insights, "referrals_total", 0))
    questions_received = _safe_int(getattr(insights, "questions_received", 0))
    questions_sent = _safe_int(getattr(insights, "questions_sent", 0))

    identity = first_name + (f" · @{username}" if username else "")
    status_line = "👑 VIP" if is_vip else "🌙 Обычный"
    rating_text = f"{reputation['score']:+.1f}%" if reputation["total"] else "нет оценок"

    text = screen(
        PROFILE_TITLE,
        intro=f"<b>{identity}</b>\n{status_line} · ⭐ <b>{stars_balance}</b> · 🏆 <b>{unlocked}/{total}</b>",
        sections=(
            section("Статус", (
                metric("⚡", "Уровень", reputation["level"]),
                metric("✨", "XP", reputation["xp"]),
                metric("⭐", "Репутация", rating_text),
                metric("🗳", "Оценок", reputation["total"]),
            )),
            section("Ключевые показатели", (
                metric("💬", "Диалогов", completed_chats),
                metric("📅", "Дней с CASPER", days_in_bot),
                metric("🎁", "Подарков", gifts_received),
                metric("👥", "Приглашений", referrals_total),
            )),
            section("Активность", (
                metric("📥", "Вопросов получено", questions_received),
                metric("✉️", "Вопросов отправлено", questions_sent),
                metric("⚠️", "Жалоб", complaints),
                metric("🚨", "Предупреждений", f"{warnings_count}/3"),
            )),
        ),
        footer="Все функции профиля собраны по разделам: активность, награды, социальное и премиум.",
    )
    return text, get_profile_keyboard(is_vip)


async def send_profile_screen(message: Message, user_id: int):
    profile_screen = await build_profile_screen(user_id)
    if profile_screen is None:
        return None
    text, keyboard = profile_screen
    return await send_brand_card(message, "profile", text, keyboard)

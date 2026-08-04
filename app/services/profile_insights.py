from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import aiosqlite

from app.database.repository import DB_PATH


@dataclass(frozen=True)
class ProfileInsights:
    days_in_bot: int = 0
    questions_sent: int = 0
    questions_received: int = 0
    questions_answered: int = 0
    answers_received: int = 0
    link_visits: int = 0
    gifts_sent: int = 0
    gifts_received: int = 0


@dataclass(frozen=True)
class Achievement:
    code: str
    icon: str
    title: str
    description: str
    unlocked: bool


async def _table_columns(conn: aiosqlite.Connection, table: str) -> set[str]:
    rows = await (await conn.execute(f"PRAGMA table_info({table})")).fetchall()
    return {str(row[1]) for row in rows}


async def _count(conn: aiosqlite.Connection, sql: str, params: tuple[object, ...]) -> int:
    row = await (await conn.execute(sql, params)).fetchone()
    return int(row[0] or 0) if row else 0


async def load_profile_insights(user_id: int, joined_at: str | None = None) -> ProfileInsights:
    days = 0
    if joined_at:
        try:
            days = max(0, (datetime.now() - datetime.fromisoformat(joined_at)).days)
        except (TypeError, ValueError):
            days = 0

    values = {
        "questions_sent": 0,
        "questions_received": 0,
        "questions_answered": 0,
        "answers_received": 0,
        "link_visits": 0,
        "gifts_sent": 0,
        "gifts_received": 0,
    }

    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        await conn.execute("PRAGMA busy_timeout=10000")

        question_columns = await _table_columns(conn, "anonymous_questions")
        if {"sender_id", "receiver_id"}.issubset(question_columns):
            values["questions_sent"] = await _count(
                conn, "SELECT COUNT(*) FROM anonymous_questions WHERE sender_id=?", (user_id,)
            )
            values["questions_received"] = await _count(
                conn, "SELECT COUNT(*) FROM anonymous_questions WHERE receiver_id=?", (user_id,)
            )
            if "status" in question_columns:
                values["questions_answered"] = await _count(
                    conn,
                    "SELECT COUNT(*) FROM anonymous_questions WHERE receiver_id=? AND status='answered'",
                    (user_id,),
                )
                values["answers_received"] = await _count(
                    conn,
                    "SELECT COUNT(*) FROM anonymous_questions WHERE sender_id=? AND status='answered'",
                    (user_id,),
                )

        visit_columns = await _table_columns(conn, "question_link_visits")
        if "owner_id" in visit_columns:
            values["link_visits"] = await _count(
                conn, "SELECT COUNT(*) FROM question_link_visits WHERE owner_id=?", (user_id,)
            )

        purchase_columns = await _table_columns(conn, "purchases")
        if {"buyer_id", "receiver_id", "type"}.issubset(purchase_columns):
            values["gifts_sent"] = await _count(
                conn,
                "SELECT COUNT(*) FROM purchases WHERE buyer_id=? AND type='gift'",
                (user_id,),
            )
            values["gifts_received"] = await _count(
                conn,
                "SELECT COUNT(*) FROM purchases WHERE receiver_id=? AND type='gift'",
                (user_id,),
            )

    return ProfileInsights(days_in_bot=days, **values)


def build_achievements(insights: ProfileInsights, *, is_vip: bool, stars_balance: int) -> tuple[Achievement, ...]:
    return (
        Achievement("welcome", "👻", "Первый шаг", "Открыть профиль CASPER", True),
        Achievement("week", "📅", "С нами неделю", "Провести в боте 7 дней", insights.days_in_bot >= 7),
        Achievement("question", "❓", "Первый вопрос", "Отправить анонимный вопрос", insights.questions_sent >= 1),
        Achievement("answer", "💬", "Первый ответ", "Ответить на анонимный вопрос", insights.questions_answered >= 1),
        Achievement("popular", "🔥", "Популярная ссылка", "Получить 10 переходов по ссылке", insights.link_visits >= 10),
        Achievement("gift", "🎁", "Даритель", "Отправить первый подарок", insights.gifts_sent >= 1),
        Achievement("collector", "🎀", "Коллекционер", "Получить 5 подарков", insights.gifts_received >= 5),
        Achievement("stars", "⭐", "Звёздный запас", "Накопить 100 звёзд", stars_balance >= 100),
        Achievement("vip", "👑", "VIP", "Активировать VIP-подписку", is_vip),
    )


def achievement_progress(achievements: tuple[Achievement, ...]) -> tuple[int, int]:
    return sum(item.unlocked for item in achievements), len(achievements)

from __future__ import annotations

import aiosqlite
from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.database.repository import DB_PATH
from .shared import db, router


INTERESTS = (
    ("music", "🎵 Музыка"),
    ("movies", "🎬 Кино"),
    ("games", "🎮 Игры"),
    ("sport", "🏃 Спорт"),
    ("books", "📚 Книги"),
    ("travel", "✈️ Путешествия"),
    ("tech", "💻 Технологии"),
    ("humor", "😂 Юмор"),
)


def _preferences_keyboard(preferences: dict[str, object]) -> InlineKeyboardMarkup:
    language = str(preferences.get("language") or "ru")
    selected = {str(item) for item in preferences.get("interests", [])}
    reconnect = bool(preferences.get("allow_reconnect", True))

    rows = [[
        InlineKeyboardButton(
            text=("✅ Русский" if language == "ru" else "🇷🇺 Русский"),
            callback_data="community_language:ru",
        ),
        InlineKeyboardButton(
            text=("✅ English" if language == "en" else "🇬🇧 English"),
            callback_data="community_language:en",
        ),
    ]]
    for index in range(0, len(INTERESTS), 2):
        row = []
        for code, title in INTERESTS[index:index + 2]:
            prefix = "✅ " if code in selected else ""
            row.append(InlineKeyboardButton(
                text=f"{prefix}{title}",
                callback_data=f"community_interest:{code}",
            ))
        rows.append(row)
    rows.append([InlineKeyboardButton(
        text=("🤝 Сохранение: вкл" if reconnect else "🚫 Сохранение: выкл"),
        callback_data="community_reconnect_toggle",
    )])
    rows.append([InlineKeyboardButton(text="⬅️ Профиль", callback_data="profile_refresh")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _preferences_text(preferences: dict[str, object]) -> str:
    language = "Русский" if preferences.get("language") == "ru" else "English"
    selected_codes = {str(item) for item in preferences.get("interests", [])}
    titles = [title for code, title in INTERESTS if code in selected_codes]
    interests = ", ".join(titles) if titles else "не выбраны"
    reconnect = "разрешено" if preferences.get("allow_reconnect", True) else "запрещено"
    return (
        "<b>🎯 Настройки общения</b>\n\n"
        f"🌐 Язык: <b>{language}</b>\n"
        f"✨ Интересы: <b>{interests}</b>\n"
        f"🤝 Взаимное сохранение: <b>{reconnect}</b>\n\n"
        "Выбери до 10 интересов. Они будут учитываться при подборе собеседника."
    )


async def _edit_preferences(callback: CallbackQuery) -> None:
    preferences = await db.get_user_preferences(callback.from_user.id)
    await callback.message.edit_text(
        _preferences_text(preferences),
        reply_markup=_preferences_keyboard(preferences),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "community_preferences")
async def community_preferences(callback: CallbackQuery):
    await callback.answer()
    await _edit_preferences(callback)


@router.callback_query(F.data.startswith("community_language:"))
async def community_language(callback: CallbackQuery):
    language = callback.data.split(":", 1)[1]
    if language not in {"ru", "en"}:
        await callback.answer("Неизвестный язык", show_alert=True)
        return
    await db.set_user_preferences(callback.from_user.id, language=language)
    await callback.answer("Язык сохранён")
    await _edit_preferences(callback)


@router.callback_query(F.data.startswith("community_interest:"))
async def community_interest(callback: CallbackQuery):
    code = callback.data.split(":", 1)[1]
    allowed = {item[0] for item in INTERESTS}
    if code not in allowed:
        await callback.answer("Неизвестный интерес", show_alert=True)
        return
    current = await db.get_user_preferences(callback.from_user.id)
    interests = [str(item) for item in current.get("interests", [])]
    if code in interests:
        interests.remove(code)
    else:
        if len(interests) >= 10:
            await callback.answer("Можно выбрать не больше 10 интересов", show_alert=True)
            return
        interests.append(code)
    await db.set_user_preferences(callback.from_user.id, interests=interests)
    await callback.answer("Интересы обновлены")
    await _edit_preferences(callback)


@router.callback_query(F.data == "community_reconnect_toggle")
async def community_reconnect_toggle(callback: CallbackQuery):
    current = await db.get_user_preferences(callback.from_user.id)
    enabled = not bool(current.get("allow_reconnect", True))
    await db.set_user_preferences(callback.from_user.id, allow_reconnect=enabled)
    await callback.answer("Настройка сохранена")
    await _edit_preferences(callback)


@router.callback_query(F.data == "community_connections")
async def community_connections(callback: CallbackQuery):
    await callback.answer()
    await db.ensure_community_schema()
    async with aiosqlite.connect(DB_PATH, timeout=10) as conn:
        row = await (
            await conn.execute(
                """SELECT COUNT(DISTINCT CASE
                       WHEN requester_id=? THEN target_id ELSE requester_id END)
                   FROM reconnect_requests
                  WHERE status='accepted' AND (requester_id=? OR target_id=?)""",
                (callback.from_user.id, callback.from_user.id, callback.from_user.id),
            )
        ).fetchone()
    total = int(row[0] or 0) if row else 0
    await callback.message.edit_text(
        "<b>🤝 Сохранённые контакты</b>\n\n"
        f"Взаимных сохранений: <b>{total}</b>\n\n"
        "Личность остаётся скрытой. Контакт появляется только после взаимного согласия.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎯 Настройки", callback_data="community_preferences")],
            [InlineKeyboardButton(text="⬅️ Профиль", callback_data="profile_refresh")],
        ]),
    )

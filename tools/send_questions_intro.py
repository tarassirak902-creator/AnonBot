from __future__ import annotations

import asyncio

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app import database as db
from app.core.config import BOT_TOKEN


INTRO_TEXT = (
    "🎉 <b>В Casper появилась новая функция!</b>\n\n"
    "Теперь у каждого пользователя есть персональная ссылка.\n\n"
    "Разместите её в описании своего профиля Telegram, чтобы другие пользователи могли:\n\n"
    "❓ Задавать вам анонимные вопросы\n"
    "🎁 Отправлять подарки\n"
    "👑 Дарить VIP\n\n"
    "Открыть свою ссылку можно в разделе:\n"
    "❓ Вопросы → 🔗 Моя ссылка"
)


async def main() -> None:
    await db.init_db()
    bot = Bot(BOT_TOKEN)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🚀 Открыть раздел «Вопросы»", callback_data="questions:home")
    ]])

    sent = 0
    failed = 0
    # Successful sends disappear from the query as they are marked. Keep the
    # offset only over failed rows that remain eligible, otherwise successful
    # rows would shrink the result set and make us skip untouched users.
    offset = 0
    try:
        while True:
            rows = await db.get_users_without_questions_intro(limit=250, offset=offset)
            if not rows:
                break
            failed_in_batch = 0
            for (user_id,) in rows:
                try:
                    await bot.send_message(
                        user_id,
                        INTRO_TEXT,
                        parse_mode="HTML",
                        reply_markup=keyboard,
                    )
                    await db.mark_questions_intro_sent(user_id)
                    sent += 1
                except Exception:
                    failed += 1
                    failed_in_batch += 1
                await asyncio.sleep(0.05)
            offset += failed_in_batch
    finally:
        await bot.session.close()

    print(f"Готово. Отправлено: {sent}; ошибок: {failed}")


if __name__ == "__main__":
    asyncio.run(main())

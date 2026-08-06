from __future__ import annotations

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.database.platform_automation_repository import PendingRating, consume_rating_token
from app.database.platform_social_repository import add_notification, rate_dialog

from .shared import router


RATING_LABELS = {
    1: ("👍", "положительную"),
    0: ("🙂", "нейтральную"),
    -1: ("👎", "отрицательную"),
}


def rating_keyboard(pending: PendingRating) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👍 Отлично", callback_data=f"dialog_rate:1:{pending.token}"),
                InlineKeyboardButton(text="🙂 Нормально", callback_data=f"dialog_rate:0:{pending.token}"),
            ],
            [InlineKeyboardButton(text="👎 Не понравилось", callback_data=f"dialog_rate:-1:{pending.token}")],
            [InlineKeyboardButton(text="✖️ Пропустить", callback_data=f"dialog_rate_skip:{pending.token}")],
        ]
    )


async def send_rating_prompt(bot, pending: PendingRating) -> None:
    await bot.send_message(
        pending.rater_id,
        "⭐ <b>Как прошло общение?</b>\n\nОценка анонимна и помогает улучшать подбор собеседников.",
        parse_mode="HTML",
        reply_markup=rating_keyboard(pending),
    )


@router.callback_query(F.data.startswith("dialog_rate:"))
async def submit_dialog_rating(callback: CallbackQuery) -> None:
    _, raw_rating, token = (callback.data or "").split(":", 2)
    try:
        rating = int(raw_rating)
    except ValueError:
        await callback.answer("Некорректная оценка.", show_alert=True)
        return
    if rating not in RATING_LABELS:
        await callback.answer("Некорректная оценка.", show_alert=True)
        return

    pending = await consume_rating_token(token, callback.from_user.id)
    if not pending:
        await callback.answer("Эта оценка уже отправлена или устарела.", show_alert=True)
        return

    saved = await rate_dialog(
        pending.rater_id,
        pending.rated_user_id,
        pending.dialog_key,
        rating,
    )
    if not saved:
        await callback.answer("Оценка уже была учтена.", show_alert=True)
        return

    emoji, label = RATING_LABELS[rating]
    await add_notification(
        pending.rated_user_id,
        "reputation",
        "Новая оценка диалога",
        f"Вы получили {label} оценку после недавнего общения.",
    )
    await callback.message.edit_text(
        f"{emoji} <b>Спасибо за оценку!</b>\n\nОна учтена в репутации собеседника.",
        parse_mode="HTML",
    )
    await callback.answer("Оценка сохранена")


@router.callback_query(F.data.startswith("dialog_rate_skip:"))
async def skip_dialog_rating(callback: CallbackQuery) -> None:
    token = (callback.data or "").split(":", 1)[1]
    pending = await consume_rating_token(token, callback.from_user.id)
    if not pending:
        await callback.answer("Действие уже выполнено.", show_alert=True)
        return
    await callback.message.edit_text("Оценка пропущена. Спасибо за общение 🙂")
    await callback.answer()

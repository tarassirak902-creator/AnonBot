from __future__ import annotations

from typing import Any

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message


_NOT_MODIFIED_MARKERS = (
    "message is not modified",
    "message not modified",
)

_EDIT_UNAVAILABLE_MARKERS = (
    "message to edit not found",
    "message can't be edited",
    "message can\'t be edited",
    "message identifier is not specified",
)


def _error_text(exc: Exception) -> str:
    return str(exc).strip().lower()


def is_message_not_modified(exc: Exception) -> bool:
    if not isinstance(exc, TelegramBadRequest):
        return False
    text = _error_text(exc)
    return any(marker in text for marker in _NOT_MODIFIED_MARKERS)


def is_edit_unavailable(exc: Exception) -> bool:
    if not isinstance(exc, TelegramBadRequest):
        return False
    text = _error_text(exc)
    return any(marker in text for marker in _EDIT_UNAVAILABLE_MARKERS)


async def render_message(
    message: Message,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = "HTML",
    prefer_edit: bool = True,
    disable_web_page_preview: bool | None = None,
) -> Message | None:
    """Render one logical screen without creating duplicate messages on refresh.

    When editing is possible, the existing bot message is reused. Telegram's
    harmless "message is not modified" response is treated as success. A new
    message is sent only when Telegram explicitly says the old message cannot
    be edited. Unexpected API errors are deliberately re-raised.
    """
    kwargs: dict[str, Any] = {
        "parse_mode": parse_mode,
        "reply_markup": reply_markup,
    }
    if disable_web_page_preview is not None:
        kwargs["disable_web_page_preview"] = disable_web_page_preview

    if prefer_edit:
        try:
            return await message.edit_text(text, **kwargs)
        except TelegramBadRequest as exc:
            if is_message_not_modified(exc):
                return None
            if not is_edit_unavailable(exc):
                raise

    return await message.answer(text, **kwargs)


async def render_callback(
    callback: CallbackQuery,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = "HTML",
    answer_text: str | None = None,
    show_alert: bool = False,
    prefer_edit: bool = True,
) -> Message | None:
    """Answer a callback once and render its destination screen consistently."""
    await callback.answer(answer_text, show_alert=show_alert)
    if callback.message is None:
        return None
    return await render_message(
        callback.message,
        text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
        prefer_edit=prefer_edit,
    )

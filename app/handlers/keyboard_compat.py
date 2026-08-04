from __future__ import annotations

from aiogram.types import Message

from . import shared


async def hide_reply_keyboard(message: Message) -> None:
    """Legacy compatibility hook.

    Reply keyboards are now collapsible, so screens with inline controls no longer
    need to send a separate removal message. Keeping this async no-op prevents old
    handlers from failing while avoiding extra service messages in the chat.
    """
    return None


def install_keyboard_compat() -> None:
    shared.hide_reply_keyboard = hide_reply_keyboard

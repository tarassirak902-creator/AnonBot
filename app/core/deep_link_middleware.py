from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message

from app.services.deep_link_context import parse_question_deep_link, pending_question_deep_links


class QuestionDeepLinkMiddleware(BaseMiddleware):
    """Remember question deep links before command handlers apply access gates."""

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        token = parse_question_deep_link(getattr(event, "text", None))
        user = getattr(event, "from_user", None)
        if token and user:
            pending_question_deep_links.put(user.id, token)
        return await handler(event, data)

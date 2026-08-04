from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence

QuestionRow = Sequence[object]
OwnerLookup = Callable[[int], Awaitable[object | None]]
QuestionLookup = Callable[[str], Awaitable[QuestionRow | None]]


class QuestionReceiverResolver:
    """Resolve and authorize a receiver for question-related commerce flows.

    Context ``t`` addresses a receiver directly by Telegram user ID. Context
    ``q`` lets the question receiver send something back to the original sender.
    Context ``a`` lets the original sender send something to the user who
    answered. Database access is injected so the rules remain independent from
    aiogram handlers and are easy to test.
    """

    def __init__(
        self,
        *,
        get_owner_by_id: OwnerLookup,
        get_question_by_public_id: QuestionLookup,
    ) -> None:
        self._get_owner_by_id = get_owner_by_id
        self._get_question_by_public_id = get_question_by_public_id

    async def resolve(self, user_id: int, context: str, reference: str) -> int | None:
        user_id = int(user_id)
        context = str(context)
        reference = str(reference)

        if context == "t":
            return await self._resolve_direct(user_id, reference)
        if context in {"q", "a"}:
            return await self._resolve_question_context(user_id, context, reference)
        return None

    async def _resolve_direct(self, user_id: int, reference: str) -> int | None:
        try:
            candidate = int(reference)
        except (TypeError, ValueError):
            return None
        if candidate <= 0 or candidate == user_id:
            return None
        owner = await self._get_owner_by_id(candidate)
        return candidate if owner is not None else None

    async def _resolve_question_context(
        self,
        user_id: int,
        context: str,
        reference: str,
    ) -> int | None:
        question = await self._get_question_by_public_id(reference)
        if not question or len(question) < 4:
            return None

        try:
            sender_id = int(question[2])
            receiver_id = int(question[3])
        except (TypeError, ValueError, IndexError):
            return None

        if context == "q" and receiver_id == user_id:
            return sender_id if sender_id != user_id else None
        if context == "a" and sender_id == user_id:
            return receiver_id if receiver_id != user_id else None
        return None

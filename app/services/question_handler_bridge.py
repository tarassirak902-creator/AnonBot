from __future__ import annotations

from collections.abc import Iterator, MutableMapping
from types import ModuleType

from .question_receiver import QuestionReceiverResolver
from .question_start_context import QuestionStartContext, QuestionStartContextStore


class QuestionStartTargetMapping(MutableMapping[int, tuple[str, int, str]]):
    """Tuple-compatible adapter for the legacy questions handler.

    The handler can keep its current ``mapping[user_id] = (...)`` API while the
    actual state is bounded and expires through ``QuestionStartContextStore``.
    This adapter is temporary and can be deleted when the handler is split.
    """

    def __init__(self, store: QuestionStartContextStore) -> None:
        self._store = store

    def __getitem__(self, user_id: int) -> tuple[str, int, str]:
        context = self._store.get(int(user_id))
        if context is None:
            raise KeyError(user_id)
        return context.token, context.owner_id, context.display_name

    def __setitem__(self, user_id: int, value: tuple[str, int, str]) -> None:
        token, owner_id, display_name = value
        self._store.put(
            int(user_id),
            QuestionStartContext(
                token=str(token),
                owner_id=int(owner_id),
                display_name=str(display_name),
            ),
        )

    def __delitem__(self, user_id: int) -> None:
        context = self._store.pop(int(user_id))
        if context is None:
            raise KeyError(user_id)

    def __iter__(self) -> Iterator[int]:
        # Iteration is intentionally not used by the handler. Returning an
        # empty iterator avoids exposing storage internals through the bridge.
        return iter(())

    def __len__(self) -> int:
        return len(self._store)

    def get(self, user_id: int, default=None):
        context = self._store.get(int(user_id))
        if context is None:
            return default
        return context.token, context.owner_id, context.display_name

    def pop(self, user_id: int, default=None):
        context = self._store.pop(int(user_id))
        if context is None:
            return default
        return context.token, context.owner_id, context.display_name



def install_question_services(
    questions_module: ModuleType,
    *,
    max_start_contexts: int = 2_000,
    start_context_ttl_seconds: float = 30 * 60,
) -> None:
    """Inject bounded state and receiver resolution into the legacy handler."""

    store = QuestionStartContextStore(
        max_entries=max_start_contexts,
        ttl_seconds=start_context_ttl_seconds,
    )
    questions_module._question_start_targets = QuestionStartTargetMapping(store)

    resolver = QuestionReceiverResolver(
        get_owner_by_id=questions_module.db.get_question_owner_by_id,
        get_question_by_public_id=questions_module.db.get_question_by_public_id,
    )

    async def resolve_question_receiver(user_id: int, context: str, reference: str) -> int | None:
        return await resolver.resolve(user_id, context, reference)

    questions_module._resolve_question_receiver = resolve_question_receiver

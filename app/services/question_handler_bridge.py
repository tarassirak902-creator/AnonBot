from __future__ import annotations

from collections.abc import Iterator, MutableMapping
from types import ModuleType

from .question_navigation import QuestionNavigation
from .question_presentation import (
    build_answer_list_items,
    build_question_list_items,
    display_owner_name,
)
from .question_receiver import QuestionReceiverResolver
from .question_start_context import QuestionStartContext, QuestionStartContextStore


class QuestionStartTargetMapping(MutableMapping[int, tuple[str, int, str]]):
    """Tuple-compatible adapter for the legacy questions handler."""

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
            QuestionStartContext(str(token), int(owner_id), str(display_name)),
        )

    def __delitem__(self, user_id: int) -> None:
        if self._store.pop(int(user_id)) is None:
            raise KeyError(user_id)

    def __iter__(self) -> Iterator[int]:
        return iter(())

    def __len__(self) -> int:
        return len(self._store)

    def get(self, user_id: int, default=None):
        context = self._store.get(int(user_id))
        return default if context is None else (context.token, context.owner_id, context.display_name)

    def pop(self, user_id: int, default=None):
        context = self._store.pop(int(user_id))
        return default if context is None else (context.token, context.owner_id, context.display_name)


def install_question_services(
    questions_module: ModuleType,
    *,
    max_start_contexts: int = 2_000,
    start_context_ttl_seconds: float = 30 * 60,
) -> None:
    """Inject service-layer behavior into the legacy question handler."""

    store = QuestionStartContextStore(
        max_entries=max_start_contexts,
        ttl_seconds=start_context_ttl_seconds,
    )
    questions_module._question_start_targets = QuestionStartTargetMapping(store)

    navigation = QuestionNavigation(page_size=int(questions_module.PAGE_SIZE))
    questions_module._question_navigation = navigation
    questions_module.PAGE_SIZE = navigation.page_size

    resolver = QuestionReceiverResolver(
        get_owner_by_id=questions_module.db.get_question_owner_by_id,
        get_question_by_public_id=questions_module.db.get_question_by_public_id,
    )

    async def resolve_question_receiver(user_id: int, context: str, reference: str) -> int | None:
        return await resolver.resolve(user_id, context, reference)

    def questions_list_inline(rows):
        items = build_question_list_items(rows)
        if not items:
            return None
        return questions_module.InlineKeyboardMarkup(
            inline_keyboard=[[
                questions_module.InlineKeyboardButton(text=item.text, callback_data=item.callback_data)
            ] for item in items]
        )

    def answers_list_inline(rows):
        items = build_answer_list_items(rows)
        if not items:
            return None
        return questions_module.InlineKeyboardMarkup(
            inline_keyboard=[[
                questions_module.InlineKeyboardButton(text=item.text, callback_data=item.callback_data)
            ] for item in items]
        )

    questions_module._resolve_question_receiver = resolve_question_receiver
    questions_module._display_name = display_owner_name
    questions_module._questions_list_inline = questions_list_inline
    questions_module._answers_list_inline = answers_list_inline

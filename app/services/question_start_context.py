from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from time import monotonic
from typing import Callable


@dataclass(frozen=True, slots=True)
class QuestionStartContext:
    token: str
    owner_id: int
    display_name: str


class QuestionStartContextStore:
    """Bounded in-memory storage for personal-link entry context.

    The current Telegram flow only needs short-lived context between opening a
    ``start=ask_...`` link and pressing the reply-menu button. Keeping this in a
    dedicated service prevents handler modules from owning unbounded global
    dictionaries and makes expiry behavior explicit and testable.
    """

    def __init__(
        self,
        *,
        max_entries: int = 2_000,
        ttl_seconds: float = 30 * 60,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._max_entries = int(max_entries)
        self._ttl_seconds = float(ttl_seconds)
        self._clock = clock
        self._items: OrderedDict[int, tuple[float, QuestionStartContext]] = OrderedDict()

    def put(self, user_id: int, context: QuestionStartContext) -> None:
        now = self._clock()
        self._prune(now)
        self._items.pop(int(user_id), None)
        self._items[int(user_id)] = (now, context)
        while len(self._items) > self._max_entries:
            self._items.popitem(last=False)

    def get(self, user_id: int) -> QuestionStartContext | None:
        now = self._clock()
        self._prune(now)
        item = self._items.get(int(user_id))
        if item is None:
            return None
        created_at, context = item
        self._items.move_to_end(int(user_id))
        return context

    def pop(self, user_id: int) -> QuestionStartContext | None:
        now = self._clock()
        self._prune(now)
        item = self._items.pop(int(user_id), None)
        return item[1] if item is not None else None

    def discard(self, user_id: int) -> None:
        self._items.pop(int(user_id), None)

    def __len__(self) -> int:
        self._prune(self._clock())
        return len(self._items)

    def _prune(self, now: float) -> None:
        expired_before = now - self._ttl_seconds
        while self._items:
            _, (created_at, _) = next(iter(self._items.items()))
            if created_at > expired_before:
                break
            self._items.popitem(last=False)

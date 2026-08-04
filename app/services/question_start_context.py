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
    """Bounded in-memory storage for personal-link entry context."""

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
        key = int(user_id)
        self._items.pop(key, None)
        self._items[key] = (now, context)
        while len(self._items) > self._max_entries:
            self._items.popitem(last=False)

    def get(self, user_id: int) -> QuestionStartContext | None:
        now = self._clock()
        self._prune(now)
        key = int(user_id)
        item = self._items.get(key)
        if item is None:
            return None
        _, context = item
        # Reads update eviction recency, but expiry remains based on the original
        # insertion timestamp. _prune therefore scans all entries instead of
        # assuming OrderedDict order is chronological.
        self._items.move_to_end(key)
        return context

    def pop(self, user_id: int) -> QuestionStartContext | None:
        self._prune(self._clock())
        item = self._items.pop(int(user_id), None)
        return item[1] if item is not None else None

    def discard(self, user_id: int) -> None:
        self._items.pop(int(user_id), None)

    def keys_snapshot(self) -> tuple[int, ...]:
        """Return active keys without exposing mutable storage internals."""
        self._prune(self._clock())
        return tuple(self._items.keys())

    def __len__(self) -> int:
        self._prune(self._clock())
        return len(self._items)

    def _prune(self, now: float) -> None:
        expired_before = now - self._ttl_seconds
        expired = [
            user_id
            for user_id, (created_at, _) in self._items.items()
            if created_at <= expired_before
        ]
        for user_id in expired:
            self._items.pop(user_id, None)

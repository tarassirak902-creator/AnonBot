from __future__ import annotations

from collections import OrderedDict
from time import monotonic


class PendingQuestionDeepLinks:
    def __init__(self, *, ttl_seconds: float = 1800, max_entries: int = 2000) -> None:
        self._ttl_seconds = float(ttl_seconds)
        self._max_entries = int(max_entries)
        self._items: OrderedDict[int, tuple[float, str]] = OrderedDict()

    def put(self, user_id: int, token: str) -> None:
        self._prune()
        key = int(user_id)
        self._items.pop(key, None)
        self._items[key] = (monotonic(), str(token))
        while len(self._items) > self._max_entries:
            self._items.popitem(last=False)

    def pop(self, user_id: int) -> str | None:
        self._prune()
        item = self._items.pop(int(user_id), None)
        return item[1] if item else None

    def _prune(self) -> None:
        threshold = monotonic() - self._ttl_seconds
        for key in [key for key, (created_at, _) in self._items.items() if created_at <= threshold]:
            self._items.pop(key, None)


def parse_question_deep_link(text: str | None) -> str | None:
    raw = (text or "").strip()
    if not raw.startswith("/start"):
        return None
    parts = raw.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].startswith("ask_"):
        return None
    return parts[1][4:].strip() or None


pending_question_deep_links = PendingQuestionDeepLinks()

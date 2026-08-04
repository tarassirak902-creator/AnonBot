from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Sequence, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Page(Generic[T]):
    items: tuple[T, ...]
    offset: int
    has_previous: bool
    has_next: bool


class QuestionNavigation:
    """Pure pagination rules for question and answer collections."""

    def __init__(self, page_size: int = 5) -> None:
        if page_size <= 0:
            raise ValueError("page_size must be positive")
        self.page_size = int(page_size)

    def normalize_offset(self, offset: int) -> int:
        return max(0, int(offset))

    def previous_offset(self, offset: int) -> int:
        return max(0, self.normalize_offset(offset) - self.page_size)

    def next_offset(self, offset: int) -> int:
        return self.normalize_offset(offset) + self.page_size

    def build_page(self, rows: Sequence[T], offset: int) -> Page[T]:
        normalized = self.normalize_offset(offset)
        items = tuple(rows[: self.page_size])
        return Page(
            items=items,
            offset=normalized,
            has_previous=normalized > 0,
            has_next=len(rows) > self.page_size,
        )

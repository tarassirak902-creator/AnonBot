import asyncio
import time
from collections import defaultdict
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, TelegramObject

from app import database as db


class AntiFloodMiddleware(BaseMiddleware):
    """Последовательно обрабатывает обновления одного пользователя и ограничивает частоту.

    Кэш служебных данных периодически очищается, чтобы длительно работающий бот не
    накапливал записи для пользователей, которые давно перестали обращаться к нему.
    """

    def __init__(self, slow_mode_delay: float = 0.25, cache_ttl: float = 3600.0):
        if slow_mode_delay < 0:
            raise ValueError("slow_mode_delay не может быть отрицательным")
        if cache_ttl <= 0:
            raise ValueError("cache_ttl должен быть положительным")

        self.slow_mode_delay = slow_mode_delay
        self.cache_ttl = cache_ttl
        self._last_update: dict[int, float] = {}
        self._locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._processed_updates = 0

    def _prune_stale_entries(self, now: float) -> None:
        stale_before = now - self.cache_ttl
        stale_user_ids = [
            user_id
            for user_id, last_seen in self._last_update.items()
            if last_seen < stale_before and not self._locks[user_id].locked()
        ]
        for user_id in stale_user_ids:
            self._last_update.pop(user_id, None)
            self._locks.pop(user_id, None)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        user_id = user.id
        if await db.is_user_blocked(user_id):
            # Заблокированный пользователь должен иметь возможность открыть
            # единственную служебную кнопку с информацией о блокировке.
            if isinstance(event, CallbackQuery) and event.data == "is_banned_alert":
                return await handler(event, data)
            if isinstance(event, CallbackQuery):
                await event.answer("⛔ Ваш аккаунт ограничен администрацией.", show_alert=True)
            return None

        lock = self._locks[user_id]
        async with lock:
            now = time.monotonic()
            wait_for = self.slow_mode_delay - (now - self._last_update.get(user_id, 0.0))
            if wait_for > 0:
                await asyncio.sleep(wait_for)

            self._last_update[user_id] = time.monotonic()
            try:
                return await handler(event, data)
            finally:
                self._processed_updates += 1
                if self._processed_updates % 1000 == 0:
                    self._prune_stale_entries(time.monotonic())

import asyncio
import logging
import time
from collections import defaultdict
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app import database as db

logger = logging.getLogger(__name__)


class UpdateObservabilityMiddleware(BaseMiddleware):
    """Log routed updates without recording private message contents."""

    def __init__(self, callback_ttl: float = 3.0, cache_ttl: float = 600.0):
        if callback_ttl <= 0:
            raise ValueError("callback_ttl должен быть положительным")
        if cache_ttl <= callback_ttl:
            raise ValueError("cache_ttl должен быть больше callback_ttl")
        self.callback_ttl = callback_ttl
        self.cache_ttl = cache_ttl
        self._callbacks: dict[str, float] = {}
        self._processed = 0

    def _prune(self, now: float) -> None:
        stale_before = now - self.cache_ttl
        for callback_id, seen_at in list(self._callbacks.items()):
            if seen_at < stale_before:
                self._callbacks.pop(callback_id, None)

    @staticmethod
    def _route(event: TelegramObject) -> str:
        if isinstance(event, CallbackQuery):
            callback_name = (event.data or "-").split(":", 1)[0][:64]
            return f"callback:{callback_name}"
        if isinstance(event, Message):
            content_type = str(event.content_type or "unknown")
            payload = event.text if event.text is not None else event.caption
            if payload is None:
                return f"message:{content_type}"
            return f"message:{content_type}:len={len(payload)}"
        return type(event).__name__

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        user_id = getattr(user, "id", None)
        route = self._route(event)
        now = time.monotonic()

        if isinstance(event, CallbackQuery):
            seen_at = self._callbacks.get(event.id)
            if seen_at is not None and now - seen_at < self.callback_ttl:
                try:
                    await event.answer()
                except Exception:
                    pass
                logger.info("duplicate_update user_id=%s route=%s", user_id, route)
                return None
            self._callbacks[event.id] = now

        logger.info("route_start user_id=%s route=%s", user_id, route)
        started = time.monotonic()
        try:
            result = await handler(event, data)
            logger.info(
                "route_done user_id=%s route=%s duration_ms=%d",
                user_id,
                route,
                int((time.monotonic() - started) * 1000),
            )
            return result
        except Exception:
            logger.exception("route_error user_id=%s route=%s", user_id, route)
            try:
                if isinstance(event, CallbackQuery):
                    await event.answer("Не удалось выполнить действие. Попробуйте ещё раз.", show_alert=True)
                elif isinstance(event, Message):
                    await event.answer("⚠️ Не удалось выполнить действие. Попробуйте ещё раз.")
            except Exception:
                pass
            return None
        finally:
            self._processed += 1
            if self._processed % 500 == 0:
                self._prune(time.monotonic())


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

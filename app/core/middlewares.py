import asyncio
import time
from collections import defaultdict
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, TelegramObject

from app import database as db


class AntiFloodMiddleware(BaseMiddleware):
    def __init__(self, slow_mode_delay: float = 0.25):
        self.slow_mode_delay = slow_mode_delay
        self._last_update = defaultdict(float)
        self._locks = defaultdict(asyncio.Lock)

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

        async with self._locks[user_id]:
            now = time.monotonic()
            wait_for = self.slow_mode_delay - (now - self._last_update[user_id])
            if wait_for > 0:
                await asyncio.sleep(wait_for)
            self._last_update[user_id] = time.monotonic()
            return await handler(event, data)

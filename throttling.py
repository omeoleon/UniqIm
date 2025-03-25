from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from typing import Callable, Dict, Awaitable, Any
from datetime import datetime, timedelta
import asyncio
from cachetools import TTLCache
import logging

logger = logging.getLogger(__name__)

class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self):
        # Кэш для хранения времени последнего запроса (10 000 записей, TTL 60 сек)
        self.user_cache = TTLCache(maxsize=10_000, ttl=60)
        self.callback_cache = TTLCache(maxsize=10_000, ttl=15)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        # Разные лимиты для сообщений и callback'ов
        if isinstance(event, Message):
            cache = self.user_cache
            limit = 3  # 3 сообщения в минуту
            key = f"msg_{user.id}"
        elif isinstance(event, CallbackQuery):
            cache = self.callback_cache
            limit = 5  # 5 callback'ов в 15 секунд
            key = f"cb_{user.id}"
        else:
            return await handler(event, data)

        # Проверяем количество запросов
        request_count = cache.get(key, 0)
        if request_count >= limit:
            logger.warning(f"Throttling user {user.id} ({request_count} requests)")
            if isinstance(event, Message):
                await event.answer("Слишком много запросов. Пожалуйста, подождите...")
            return

        # Увеличиваем счетчик
        cache[key] = request_count + 1

        return await handler(event, data)
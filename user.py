from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from typing import Callable, Dict, Awaitable, Any
from database.models import User
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class UserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем информацию о пользователе
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        try:
            # Регистрируем или обновляем пользователя
            db_user, created = await User.get_or_create(
                id=user.id,
                defaults={
                    'username': user.username,
                    'full_name': user.full_name,
                    'last_active': datetime.now()
                }
            )

            if not created:
                updates = {}
                if user.username != db_user.username:
                    updates['username'] = user.username
                if user.full_name != db_user.full_name:
                    updates['full_name'] = user.full_name
                
                if updates:
                    updates['last_active'] = datetime.now()
                    await db_user.update_from_dict(updates).save()

            # Добавляем пользователя в данные
            data['db_user'] = db_user
            logger.debug(f"User processed: {user.id}")

        except Exception as e:
            logger.error(f"User middleware error: {e}", exc_info=True)
            # Продолжаем обработку даже при ошибке
            data['db_user'] = None

        return await handler(event, data)
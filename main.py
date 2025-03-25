import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.callback_answer import CallbackAnswerMiddleware
from middlewares import UserMiddleware, ThrottlingMiddleware

from config import config
from database.db import init_db, close_db
from handlers import (
    start,
    profile,
    process_video,
    support,
    admin,
    payments
)
from handlers.payments import payment_system
from services.notifications import NotificationService
from services.cleanup import file_cleanup

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

async def on_startup(bot: Bot):
    """Действия при запуске бота"""
    try:
        # Инициализация БД
        await init_db()
        
        # Установка username бота
        bot_info = await bot.get_me()
        config.BOT_USERNAME = bot_info.username
        logger.info(f"Bot @{config.BOT_USERNAME} started")
        
        # Запуск фоновых задач
        asyncio.create_task(payment_system.start_payment_checker(bot))
        asyncio.create_task(NotificationService(bot).start_periodic_check())
        asyncio.create_task(file_cleanup.run_periodic_cleanup())
        
        # Настройка платежного webhook (если используется)
        if config.WEBHOOK_HOST:
            await payment_system.setup_webhook()
        
    except Exception as e:
        logger.error(f"Startup error: {e}", exc_info=True)
        raise

async def on_shutdown(bot: Bot):
    """Действия при остановке бота"""
    try:
        await close_db()
        await bot.session.close()
        logger.info("Bot stopped gracefully")
    except Exception as e:
        logger.error(f"Shutdown error: {e}")

def setup_handlers(dp: Dispatcher):
    """Регистрация всех обработчиков"""
    dp.include_router(start.router)
    dp.include_router(profile.router)
    dp.include_router(process_video.router)
    dp.include_router(support.router)
    dp.include_router(payments.router)
    dp.include_router(admin.router)

def setup_middlewares(dp: Dispatcher):
    """Настройка middleware"""
    # Порядок важен! Первый добавленный обрабатывается первым
    dp.update.outer_middleware(UserMiddleware())
    dp.update.middleware(ThrottlingMiddleware())

async def main():
    """Основная функция запуска бота"""
    # Инициализация бота с новым синтаксисом
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Настройка middleware
    dp.callback_query.middleware(CallbackAnswerMiddleware())
    setup_middlewares(dp)
    
    # Регистрация обработчиков
    setup_handlers(dp)
    
    # Настройка событий запуска/остановки
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    try:
        # Запуск поллинга
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

async def on_startup(bot: Bot):
    try:
        await init_db()
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
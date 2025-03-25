import logging
from pathlib import Path
from tortoise import Tortoise, fields, run_async
from tortoise.contrib.fastapi import register_tortoise
from tortoise.exceptions import DBConnectionError, ConfigurationError
from config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Определяем модели для инициализации
DB_MODELS = ["database.models"]
if config.USE_MIGRATIONS:
    DB_MODELS.append("aerich.models")  # Добавляем только если используются миграции

TORTOISE_ORM = {
    "connections": {
        "default": {
            "engine": "tortoise.backends.sqlite",
            "credentials": {
                "file_path": str(config.DB_PATH),
                "journal_mode": "WAL",
                "timeout": 30,
            }
        }
    },
    "apps": {
        "models": {
            "models": ["database.models"],
            "default_connection": "default",
        }
    },
    "use_tz": True,
    "timezone": "UTC",
}

async def init_db():
    """Инициализация БД с гарантированным созданием таблиц"""
    try:
        # Удаляем старую БД если существует (для теста)
        if config.DB_PATH.exists():
            config.DB_PATH.unlink()
        
        # Создаем директорию
        config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initializing database at {config.DB_PATH}")
        
        # Инициализация Tortoise
        await Tortoise.init(config=TORTOISE_ORM)
        
        # Принудительное создание таблиц
        await Tortoise.generate_schemas()
        
        logger.info("Database tables created successfully")
        
        # Проверяем существование таблицы users
        if not await check_table_exists("users"):
            raise DBConnectionError("Failed to create users table")
            
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

async def check_table_exists(table_name: str) -> bool:
    """Проверка существования таблицы"""
    try:
        conn = Tortoise.get_connection("default")
        tables = await conn.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?;",
            [table_name]
        )
        return len(tables) > 0
    except Exception as e:
        logger.error(f"Table check failed: {e}")
        return False

async def close_db():
    """Закрытие соединений"""
    await Tortoise.close_connections()
    logger.info("Database connections closed")
def register_db(app):
    """Регистрация Tortoise ORM в FastAPI приложении"""
    try:
        register_tortoise(
            app,
            config=TORTOISE_ORM,
            generate_schemas=True,
            add_exception_handlers=True,
        )
        logger.info("Tortoise ORM registered with FastAPI")
    except Exception as e:
        logger.error(f"Failed to register Tortoise ORM: {e}")
        raise

async def execute_query(query: str, params: dict = None):
    """Безопасное выполнение SQL запроса с обработкой ошибок"""
    try:
        conn = Tortoise.get_connection("default")
        result = await conn.execute_query(query, params)
        return result
    except Exception as e:
        logger.error(f"Query execution failed: {e}\nQuery: {query}")
        raise

async def health_check():
    """Проверка работоспособности БД с таймаутом"""
    try:
        # Проверяем соединение простым запросом
        await execute_query("SELECT 1")
        return True
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        return False

async def backup_db(backup_path: Path):
    """Создание резервной копии базы данных"""
    try:
        import shutil
        shutil.copy2(config.DB_PATH, backup_path)
        logger.info(f"Database backup created at {backup_path}")
        return True
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        return False

if __name__ == '__main__':
    # Тестирование подключения к БД
    async def test_db():
        try:
            await init_db()
            print(f"Database health: {'OK' if await health_check() else 'FAILED'}")
            
            # Пример создания тестового пользователя
            from database.models import User
            user = await User.create(id=1, username="test_user")
            print(f"Created test user: {user}")
            
            await close_db()
        except Exception as e:
            print(f"Test failed: {e}")
            await close_db()
    
    run_async(test_db())
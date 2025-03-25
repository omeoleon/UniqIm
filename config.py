import os
from pathlib import Path
from typing import List, Optional, Set
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()

class Config:
    def __init__(self):

        self.USE_MIGRATIONS: bool = self._get_bool('USE_MIGRATIONS', default=True)
        # Основные настройки бота
        self.BOT_TOKEN: str = self._get_env_var('BOT_TOKEN', required=True)
        self.ADMIN_IDS: Set[int] = self._parse_admin_ids()
        self.BOT_USERNAME: Optional[str] = None  # Будет установлено автоматически

        self.DB_MODELS: List[str] = ["database.models"]  # Путь к моделям

        # Настройки базы данных
        self.DB_PATH: Path = Path('database/bot_database.db')
        self.DB_ECHO: bool = self._get_bool('DB_ECHO', default=False)
        self.DB_TIMEZONE: str = self._get_env_var('DB_TIMEZONE', default='UTC')
        
        # Настройки платежной системы (Lolz.live)
        self.LOLZ_API_KEY: str = self._get_env_var('LOLZ_API_KEY', required=True)
        self.LOLZ_SECRET_KEY: str = self._get_env_var('LOLZ_SECRET_KEY', required=True)
        self.LOLZ_CALLBACK_URL: Optional[str] = self._get_env_var('LOLZ_CALLBACK_URL')
        
        # Настройки обработки видео
        self.VIDEO_PRICE: int = 30  # Стоимость обработки в рублях
        self.MAX_VIDEO_SIZE: int = 1024 * 1024 * 1024  # 1GB
        self.ALLOWED_EXTENSIONS: Set[str] = {'mp4', 'mov', 'avi', 'mkv'}
        self.TEMP_DIR: Path = Path('temp_files')
        self.PROCESSED_DIR: Path = Path('processed_videos')
        
        # Настройки кэширования
        self.CACHE_TTL: int = 24 * 3600  # 24 часа в секундах
        self.CACHE_MAX_SIZE: int = 10 * 1024 * 1024 * 1024  # 10GB
        
        # Бонусная система
        self.START_BONUS: int = 50  # Стартовый бонус для новых пользователей
        self.REFERRAL_BONUS: int = 30  # Бонус за приглашенного пользователя
        
        # Настройки вебхуков (если используются)
        self.WEBHOOK_HOST: Optional[str] = self._get_env_var('WEBHOOK_HOST')
        self.WEBHOOK_PATH: str = self._get_env_var('WEBHOOK_PATH', default='/webhook')
        self.WEBHOOK_SECRET: Optional[str] = self._get_env_var('WEBHOOK_SECRET')
        
        # Создаем необходимые директории
        self._setup_dirs()

    def _get_env_var(self, var_name: str, default: Optional[str] = None, required: bool = False) -> str:
        """Получение переменной окружения с проверкой"""
        value = os.getenv(var_name, default)
        if required and not value:
            raise ValueError(f'Необходимо указать {var_name} в .env файле')
        return value

    def _get_bool(self, var_name: str, default: bool = False) -> bool:
        """Получение булевой переменной окружения"""
        value = os.getenv(var_name, str(default)).lower()
        return value in ('true', '1', 'yes')

    def _parse_admin_ids(self) -> Set[int]:
        """Парсинг ID администраторов из переменной окружения"""
        admins = self._get_env_var('ADMIN_IDS', '').split(',')
        return {int(admin.strip()) for admin in admins if admin.strip().isdigit()}

    def _setup_dirs(self):
        """Создание необходимых директорий"""
        try:
            self.TEMP_DIR.mkdir(exist_ok=True, parents=True)
            self.PROCESSED_DIR.mkdir(exist_ok=True, parents=True)
            self.DB_PATH.parent.mkdir(exist_ok=True, parents=True)
        except OSError as e:
            raise RuntimeError(f"Ошибка при создании директорий: {e}")

    @property
    def webhook_url(self) -> Optional[str]:
        """Полный URL вебхука"""
        if self.WEBHOOK_HOST:
            return f"https://{self.WEBHOOK_HOST}{self.WEBHOOK_PATH}"
        return None

# Создаем экземпляр конфигурации
config = Config()
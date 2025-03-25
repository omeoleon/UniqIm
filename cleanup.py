import os
import time
from pathlib import Path
import logging
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor
from config import config
import sqlite3
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FileCleanup:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.temp_dir = config.TEMP_DIR
        self.processed_dir = config.PROCESSED_DIR
        self.cache_db = config.DB_PATH.parent / "video_cache.db"
        
    async def run_cleanup(self):
        """Основной метод запуска очистки"""
        try:
            await self.clean_temp_files()
            await self.clean_old_cache_entries()
            await self.clean_empty_dirs()
            logger.info("Cleanup completed successfully")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

    async def clean_temp_files(self, max_age_hours: int = 24):
        """Очистка временных файлов старше указанного возраста"""
        def _clean_files():
            now = time.time()
            deleted = 0
            
            for file_path in self._find_files(self.temp_dir):
                file_age = now - file_path.stat().st_mtime
                if file_age > max_age_hours * 3600:
                    try:
                        file_path.unlink()
                        deleted += 1
                    except OSError as e:
                        logger.warning(f"Could not delete {file_path}: {e}")
            
            return deleted
        
        deleted = await self._run_in_thread(_clean_files)
        logger.info(f"Deleted {deleted} temp files older than {max_age_hours}h")

    async def clean_old_cache_entries(self):
        """Очистка устаревших записей кэша и связанных файлов"""
        def _clean_cache():
            now = time.time()
            deleted_files = 0
            deleted_entries = 0
            
            with sqlite3.connect(self.cache_db) as conn:
                # Находим записи с истекшим TTL
                cursor = conn.execute("""
                    SELECT processed_path FROM cache 
                    WHERE timestamp < ?
                """, (now - config.CACHE_TTL,))
                
                for (file_path,) in cursor.fetchall():
                    path = Path(file_path)
                    if path.exists():
                        try:
                            path.unlink()
                            deleted_files += 1
                        except OSError as e:
                            logger.warning(f"Could not delete cache file {path}: {e}")
                
                # Удаляем записи из БД
                cursor = conn.execute("""
                    DELETE FROM cache 
                    WHERE timestamp < ?
                """, (now - config.CACHE_TTL,))
                deleted_entries = cursor.rowcount
                conn.commit()
            
            return deleted_files, deleted_entries
        
        deleted_files, deleted_entries = await self._run_in_thread(_clean_cache)
        logger.info(f"Cleaned cache: {deleted_files} files and {deleted_entries} DB entries removed")

    async def clean_empty_dirs(self):
        """Удаление пустых директорий"""
        def _clean_dirs():
            deleted = 0
            for root, dirs, _ in os.walk(self.temp_dir, topdown=False):
                for dir_name in dirs:
                    dir_path = Path(root) / dir_name
                    try:
                        if not any(dir_path.iterdir()):
                            dir_path.rmdir()
                            deleted += 1
                    except OSError as e:
                        logger.warning(f"Could not remove dir {dir_path}: {e}")
            return deleted
        
        deleted = await self._run_in_thread(_clean_dirs)
        logger.info(f"Removed {deleted} empty directories")

    async def clean_user_files(self, user_id: int, pattern: str = "*"):
        """Очистка файлов конкретного пользователя"""
        def _clean_user():
            deleted = 0
            for file_path in self.temp_dir.glob(f"{user_id}_{pattern}"):
                try:
                    file_path.unlink()
                    deleted += 1
                except OSError as e:
                    logger.warning(f"Could not delete user file {file_path}: {e}")
            return deleted
        
        deleted = await self._run_in_thread(_clean_user)
        logger.info(f"Deleted {deleted} files for user {user_id}")

    def _find_files(self, directory: Path, pattern: str = "*") -> List[Path]:
        """Рекурсивный поиск файлов по шаблону"""
        files = []
        for entry in directory.glob(pattern):
            if entry.is_file():
                files.append(entry)
        return files

    async def _run_in_thread(self, func):
        """Запуск блокирующей операции в отдельном потоке"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, func)

    def __del__(self):
        self.executor.shutdown(wait=False)

# Глобальный экземпляр для использования в системе
file_cleanup = FileCleanup()
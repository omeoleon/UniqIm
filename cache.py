import hashlib
import json
import os
import time
from pathlib import Path
from typing import Optional, Dict, Tuple
import logging
from config import config
import sqlite3
from functools import lru_cache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VideoCache:
    def __init__(self):
        self.cache_dir = config.PROCESSED_DIR
        self.cache_db = config.DB_PATH.parent / "video_cache.db"
        self._init_db()
        
    def _init_db(self):
        """Инициализация базы данных кэша"""
        with sqlite3.connect(self.cache_db) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    hash TEXT PRIMARY KEY,
                    original_path TEXT NOT NULL,
                    processed_path TEXT NOT NULL,
                    method TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    size INTEGER NOT NULL,
                    access_count INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON cache(timestamp)
            """)
            conn.commit()

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Вычисление хэша файла эффективным способом с чанкированием"""
        h = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()

    def get_cached_video(self, original_path: Path, method: str) -> Optional[Path]:
        """
        Поиск кэшированной версии видео.
        Возвращает путь к обработанному файлу, если он есть в кэше.
        """
        file_hash = self._calculate_file_hash(original_path)
        
        with sqlite3.connect(self.cache_db) as conn:
            cursor = conn.execute("""
                SELECT processed_path FROM cache 
                WHERE hash = ? AND method = ?
            """, (file_hash, method))
            
            if result := cursor.fetchone():
                processed_path = Path(result[0])
                if processed_path.exists():
                    # Обновляем статистику использования
                    conn.execute("""
                        UPDATE cache SET 
                        access_count = access_count + 1,
                        timestamp = ?
                        WHERE hash = ?
                    """, (time.time(), file_hash))
                    conn.commit()
                    return processed_path
                else:
                    self._remove_cache_entry(file_hash)
        
        return None

    def add_to_cache(self, original_path: Path, processed_path: Path, method: str) -> bool:
        """
        Добавление обработанного видео в кэш.
        Возвращает True при успешном добавлении.
        """
        if not processed_path.exists():
            return False
            
        file_hash = self._calculate_file_hash(original_path)
        file_size = processed_path.stat().st_size
        
        with sqlite3.connect(self.cache_db) as conn:
            try:
                conn.execute("""
                    INSERT INTO cache (hash, original_path, processed_path, method, timestamp, size)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    file_hash,
                    str(original_path),
                    str(processed_path),
                    method,
                    time.time(),
                    file_size
                ))
                conn.commit()
                self._cleanup_cache()
                return True
            except sqlite3.IntegrityError:
                return False

    def _remove_cache_entry(self, file_hash: str) -> bool:
        """Удаление записи из кэша"""
        with sqlite3.connect(self.cache_db) as conn:
            cursor = conn.execute("""
                DELETE FROM cache WHERE hash = ?
            """, (file_hash,))
            conn.commit()
            return cursor.rowcount > 0

    def _cleanup_cache(self):
        """Очистка кэша по правилам TTL и максимальному размеру"""
        current_time = time.time()
        total_size = 0
        
        with sqlite3.connect(self.cache_db) as conn:
            # Удаляем просроченные записи
            conn.execute("""
                DELETE FROM cache 
                WHERE timestamp < ?
            """, (current_time - config.CACHE_TTL,))
            
            # Получаем все записи в порядке использования
            cursor = conn.execute("""
                SELECT hash, size FROM cache 
                ORDER BY timestamp ASC
            """)
            
            # Проверяем общий размер кэша
            entries = cursor.fetchall()
            total_size = sum(size for _, size in entries)
            
            # Удаляем самые старые записи, если превышен лимит
            while total_size > config.CACHE_MAX_SIZE and entries:
                oldest_hash, oldest_size = entries.pop(0)
                conn.execute("""
                    DELETE FROM cache WHERE hash = ?
                """, (oldest_hash,))
                total_size -= oldest_size
                
                # Удаляем файл
                oldest_path = self._get_file_path_by_hash(oldest_hash)
                if oldest_path and oldest_path.exists():
                    try:
                        oldest_path.unlink()
                    except OSError as e:
                        logger.error(f"Error deleting cache file {oldest_path}: {e}")
            
            conn.commit()

    def _get_file_path_by_hash(self, file_hash: str) -> Optional[Path]:
        """Получение пути к файлу по его хэшу"""
        with sqlite3.connect(self.cache_db) as conn:
            cursor = conn.execute("""
                SELECT processed_path FROM cache WHERE hash = ?
            """, (file_hash,))
            if result := cursor.fetchone():
                return Path(result[0])
        return None

    def get_cache_stats(self) -> Dict[str, int]:
        """Получение статистики кэша"""
        with sqlite3.connect(self.cache_db) as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(size) as total_size,
                    SUM(access_count) as total_access
                FROM cache
            """)
            stats = dict(zip(
                ['total_entries', 'total_size', 'total_access'],
                cursor.fetchone()
            ))
            
            cursor = conn.execute("""
                SELECT method, COUNT(*) FROM cache GROUP BY method
            """)
            stats['methods'] = {row[0]: row[1] for row in cursor.fetchall()}
            
            return stats

# Глобальный экземпляр кэша
video_cache = VideoCache()
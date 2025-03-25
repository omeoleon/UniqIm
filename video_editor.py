import os
import subprocess
import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, Optional
import logging
from config import config
import ffmpeg
import tempfile
from concurrent.futures import ThreadPoolExecutor
import asyncio


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VideoEditor:
    def __init__(self):
        self.temp_dir = config.TEMP_DIR
        self.executor = ThreadPoolExecutor(max_workers=2)
        
    async def process_video(self, input_path: Path, method: str) -> Path:
        """Основной метод обработки видео"""
        methods = {
            'crocodile': self._crocodile_room,
            'dolphin': self._dolphin_room,
            'grizzly': self._grizzly_room
        }
        
        if method not in methods:
            raise ValueError(f"Unknown method: {method}")
        
        output_path = self.temp_dir / f"processed_{method}_{input_path.name}"
        
        try:
            # Обработка в отдельном потоке для избежания блокировки event loop
            processed_path = await self.run_in_thread(
                methods[method], 
                input_path, 
                output_path
            )
            self._clean_metadata(processed_path)
            return processed_path
        except Exception as e:
            logger.error(f"Error processing video: {e}")
            raise

    async def run_in_thread(self, func, *args):
        """Запуск блокирующих операций в отдельном потоке"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, func, *args)

    def _crocodile_room(self, input_path: Path, output_path: Path) -> Path:
        """Изменение контраста, насыщенности, размытие и отзеркаливание"""
        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_file:
            # Первый проход: обработка цветов и эффектов
            (
                ffmpeg.input(str(input_path))
                .filter('contrast', contrast=1.1)
                .filter('saturation', saturation=1.2)
                .filter('brightness', brightness=0.05)
                .filter('hflip')  # Горизонтальное отзеркаливание
                .filter('gblur', sigma=0.8)
                .output(temp_file.name, **self._get_output_params())
                .run(quiet=True)
            )
            
            # Второй проход: оптимизация
            self._optimize_video(temp_file.name, output_path)
        return output_path

    def _dolphin_room(self, input_path: Path, output_path: Path) -> Path:
        """Добавление шума, fade-in и масштабирование"""
        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_file:
            (
                ffmpeg.input(str(input_path))
                .filter('noise', alls=20, allf='t')
                .filter('fade', type='in', start_frame=0, nb_frames=25)
                .filter('scale', w='iw*0.95', h='ih*0.95')
                .output(temp_file.name, **self._get_output_params())
                .run(quiet=True)
            )
            self._optimize_video(temp_file.name, output_path)
        return output_path

    def _grizzly_room(self, input_path: Path, output_path: Path) -> Path:
        """Замедление/ускорение и обрезка концов"""
        duration = float(ffmpeg.probe(input_path)['format']['duration'])
        
        # Автоматическое определение параметров
        speed = 0.8 if duration < 30 else 1.2
        cut_duration = min(3, duration * 0.1)
        
        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_file:
            (
                ffmpeg.input(str(input_path))
                .filter('setpts', f'{1/speed}*PTS')
                .trim(start=cut_duration, end=duration-cut_duration)
                .setpts('PTS-STARTPTS')
                .output(temp_file.name, **self._get_output_params())
                .run(quiet=True)
            )
            self._optimize_video(temp_file.name, output_path)
        return output_path

    def _clean_metadata(self, file_path: Path):
        """Очистка метаданных с сохранением качества"""
        temp_path = file_path.with_stem(f"{file_path.stem}_clean")
        (
            ffmpeg.input(str(file_path))
            .output(str(temp_path), codec='copy', map_metadata='-1')
            .run(quiet=True)
        )
        os.replace(temp_path, file_path)

    def _optimize_video(self, input_path: str, output_path: Path):
        """Оптимизация видео для уменьшения размера"""
        (
            ffmpeg.input(input_path)
            .output(
                str(output_path),
                **self._get_output_params(),
                movflags='faststart',
                preset='slow',
                crf=23
            )
            .run(quiet=True)
        )

    def _get_output_params(self) -> dict:
        """Параметры вывода для FFmpeg"""
        return {
            'c:v': 'libx264',
            'c:a': 'aac',
            'strict': 'experimental',
            'threads': '2',
            'pix_fmt': 'yuv420p',
            'max_muxing_queue_size': '1024'
        }

    def __del__(self):
        self.executor.shutdown(wait=True)
import logging
from pathlib import Path
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime
from typing import Optional  # Добавьте этот импорт

from config import config
from database.models import User, VideoProcessing
from services.video_editor import VideoEditor
from services.cache import video_cache
from handlers.payments import payment_system
from utils.states import VideoProcessingStates
from utils.helpers import format_timedelta

router = Router()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

video_editor = VideoEditor()

@router.message(Command("process"))
async def start_video_processing(message: Message, state: FSMContext):
    """Начало процесса обработки видео"""
    user = await User.get(message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйтесь с помощью /start")
        return

    if user.balance < config.VIDEO_PRICE:
        await message.answer(
            f"Недостаточно средств. Требуется {config.VIDEO_PRICE} RUB\n"
            "Пополните баланс через /pay"
        )
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="🐊 Crocodile Room", callback_data="method_crocodile")
    builder.button(text="🐬 Dolphin Room", callback_data="method_dolphin")
    builder.button(text="🐻 Grizzly Room", callback_data="method_grizzly")
    builder.adjust(1)

    await message.answer(
        "🎬 Выберите метод обработки видео:\n\n"
        "🐊 <b>Crocodile Room</b> - цветокоррекция, эффекты\n"
        "🐬 <b>Dolphin Room</b> - шумы, анимации\n"
        "🐻 <b>Grizzly Room</b> - изменение скорости, обрезка",
        reply_markup=builder.as_markup()
    )
    await state.set_state(VideoProcessingStates.waiting_for_method)

@router.callback_query(F.data.startswith("method_"), VideoProcessingStates.waiting_for_method)
async def select_method(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора метода"""
    method = callback.data.split("_")[1]
    await state.update_data(method=method)
    await callback.message.edit_text(
        f"Выбран метод: {method.capitalize()} Room\n"
        "Теперь отправьте видео для обработки (до 1GB)"
    )
    await state.set_state(VideoProcessingStates.waiting_for_video)
    await callback.answer()

@router.message(F.video, VideoProcessingStates.waiting_for_video)
async def process_video_message(message: Message, state: FSMContext):
    """Обработка полученного видео"""
    user = await User.get(message.from_user.id)
    if not user or user.balance < config.VIDEO_PRICE:
        await message.answer("Ошибка: недостаточно средств или пользователь не найден")
        await state.clear()
        return

    try:
        data = await state.get_data()
        method = data["method"]
        
        # Проверяем кэш
        file_id = message.video.file_id
        file_name = message.video.file_name or f"video_{file_id}.mp4"
        
        # Скачиваем видео
        await message.answer("⏳ Скачиваю видео...")
        file_path = await _download_video(message.bot, file_id, file_name)
        
        if not file_path:
            await message.answer("Ошибка при скачивании видео")
            await state.clear()
            return

        # Проверяем кэш
        if cached_path := video_cache.get_cached_video(file_path, method):
            await message.answer("♻️ Использую кэшированную версию...")
            output_path = cached_path
        else:
            # Списываем средства
            await user.update(balance=user.balance - config.VIDEO_PRICE).apply()
            
            # Обрабатываем видео
            await message.answer(f"🛠️ Обрабатываю видео методом {method}...")
            output_path = await video_editor.process_video(file_path, method)
            
            # Добавляем в кэш
            video_cache.add_to_cache(file_path, output_path, method)

        # Записываем статистику
        await VideoProcessing.create(
            user_id=user.id,
            method=method,
            original_file=file_name,
            processed_file=output_path.name,
            file_size=output_path.stat().st_size
        )

        # Отправляем результат
        with open(output_path, "rb") as video_file:
            await message.answer_video(
                video=video_file,
                caption=f"✅ Готово! Метод: {method.capitalize()} Room\n"
                       f"💵 Списано: {config.VIDEO_PRICE} RUB\n"
                       f"💰 Ваш баланс: {user.balance - config.VIDEO_PRICE} RUB"
            )

    except Exception as e:
        logger.error(f"Video processing error: {e}", exc_info=True)
        await message.answer("Произошла ошибка при обработке видео")
    finally:
        await state.clear()

async def _download_video(bot, file_id: str, file_name: str) -> Optional[Path]:
    """Скачивание видео с проверкой размера"""
    try:
        file = await bot.get_file(file_id)
        if file.file_size > config.MAX_VIDEO_SIZE:
            return None

        download_path = config.TEMP_DIR / file_name
        await bot.download_file(file.file_path, destination=download_path)
        return download_path
    except Exception as e:
        logger.error(f"Download error: {e}")
        return None

@router.message(F.document, VideoProcessingStates.waiting_for_video)
async def process_video_document(message: Message, state: FSMContext):
    """Обработка видео, отправленного как документ"""
    if message.document.mime_type and "video" in message.document.mime_type:
        # Создаем объект video для совместимости
        message.video = message.document
        await process_video_message(message, state)
    else:
        await message.answer("Пожалуйста, отправьте видео файл")
        await state.clear()

@router.callback_query(F.data == "cancel_processing")
async def cancel_processing(callback: CallbackQuery, state: FSMContext):
    """Отмена обработки видео"""
    await state.clear()
    await callback.message.edit_text("❌ Обработка видео отменена")
    await callback.answer()
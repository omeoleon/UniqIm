import logging
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta
from typing import Optional

from config import config
from database.models import User, Payment, VideoProcessing, Referral
from services.payments import payment_system
from utils.helpers import format_rub, format_bytes

router = Router()
logger = logging.getLogger(__name__)

# Проверка прав администратора
ADMIN_IDS = config.ADMIN_IDS

# Middleware для проверки админских прав
@router.message.middleware
async def admin_check_middleware(handler, event, data):
    if event.from_user.id not in ADMIN_IDS:
        await event.answer("⛔ Доступ запрещен")
        return
    return await handler(event, data)

@router.message(Command("admin"))
async def admin_panel(message: types.Message):
    """Главное меню админ-панели"""
    builder = InlineKeyboardBuilder()
    buttons = [
        ("👥 Пользователи", "admin_users"),
        ("💰 Финансы", "admin_finance"),
        ("📊 Статистика", "admin_stats"),
        ("📢 Рассылка", "admin_broadcast"),
        ("⚙️ Настройки", "admin_settings")
    ]
    
    for text, callback_data in buttons:
        builder.button(text=text, callback_data=callback_data)
    builder.adjust(2)
    
    await message.answer(
        "🔐 <b>Админ-панель</b>\n\n"
        "Выберите раздел:",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data == "admin_users")
async def admin_users(callback: types.CallbackQuery):
    """Управление пользователями"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Изменить баланс", callback_data="user_balance_edit")
    builder.button(text="🔍 Поиск пользователя", callback_data="user_search")
    builder.button(text="📋 Топ активных", callback_data="user_top")
    builder.button(text="🔙 Назад", callback_data="admin_back")
    builder.adjust(1)
    
    total_users = await User.all().count()
    active_today = await User.filter(
        last_active__gte=datetime.now() - timedelta(days=1)
    ).count()
    
    await callback.message.edit_text(
        f"👥 <b>Пользователи</b>\n\n"
        f"Всего: {total_users}\n"
        f"Активных за сутки: {active_today}\n\n"
        "Выберите действие:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "admin_finance")
async def admin_finance(callback: types.CallbackQuery):
    """Финансовая статистика"""
    builder = InlineKeyboardBuilder()
    builder.button(text="💸 Все транзакции", callback_data="finance_all")
    builder.button(text="📅 За период", callback_data="finance_period")
    builder.button(text="🔙 Назад", callback_data="admin_back")
    builder.adjust(1)
    
    total_payments = await Payment.filter(status="paid").count()
    total_amount = await Payment.filter(status="paid").sum("amount") or 0
    today_amount = await Payment.filter(
        status="paid",
        paid_at__gte=datetime.now().replace(hour=0, minute=0, second=0)
    ).sum("amount") or 0
    
    await callback.message.edit_text(
        f"💰 <b>Финансы</b>\n\n"
        f"Всего платежей: {total_payments}\n"
        f"Общая сумма: {format_rub(total_amount)}\n"
        f"Сегодня: {format_rub(today_amount)}\n\n"
        "Выберите действие:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    """Статистика бота"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🎥 Видео", callback_data="stats_videos")
    builder.button(text="👥 Рефералы", callback_data="stats_refs")
    builder.button(text="🔙 Назад", callback_data="admin_back")
    builder.adjust(1)
    
    videos_processed = await VideoProcessing.all().count()
    refs_count = await Referral.all().count()
    
    await callback.message.edit_text(
        f"📊 <b>Статистика</b>\n\n"
        f"Обработано видео: {videos_processed}\n"
        f"Рефералов: {refs_count}\n\n"
        "Выберите раздел:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: types.CallbackQuery):
    """Рассылка сообщений"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Всем пользователям", callback_data="broadcast_all")
    builder.button(text="🎯 По фильтру", callback_data="broadcast_filter")
    builder.button(text="🔙 Назад", callback_data="admin_back")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "📢 <b>Рассылка сообщений</b>\n\n"
        "Выберите тип рассылки:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "admin_back")
async def admin_back(callback: types.CallbackQuery):
    """Возврат в главное меню"""
    await admin_panel(callback.message)
    await callback.answer()

# Дополнительные обработчики
@router.callback_query(F.data == "user_balance_edit")
async def user_balance_edit(callback: types.CallbackQuery):
    """Изменение баланса пользователя"""
    await callback.message.edit_text(
        "Введите ID пользователя и сумму через пробел:\n"
        "Пример: <code>123456789 500</code>"
    )
    # Здесь нужно добавить FSM для обработки ввода
    await callback.answer("Реализуйте FSM-обработчик")

@router.callback_query(F.data == "stats_videos")
async def stats_videos(callback: types.CallbackQuery):
    """Статистика по видео"""
    methods = await VideoProcessing.all().group_by("method").count()
    stats_text = "🎥 <b>Статистика видео</b>\n\n"
    
    for method, count in methods.items():
        stats_text += f"{method}: {count}\n"
    
    await callback.message.edit_text(stats_text)
    await callback.answer()

__all__ = ['router']
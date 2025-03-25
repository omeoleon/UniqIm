import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime
from aiogram.fsm.context import FSMContext
import asyncio
from utils.states import PaymentStates

from config import config
from database.models import User, Payment, VideoProcessing, Referral
from handlers.payments import payment_system
from utils.helpers import format_rub
from utils.states import PaymentStates

router = Router()
logger = logging.getLogger(__name__)

@router.message(Command("profile"))
async def show_profile(message: Message):
    """Отображение профиля пользователя с балансом и статистикой"""
    try:
        user, created = await User.get_or_create(
            id=message.from_user.id,
            defaults={
                'username': message.from_user.username,
                'full_name': message.from_user.full_name,
                'balance': 0.0,
                'registered_at': datetime.now()
            }
        )
        
        # Получаем статистику одним запросом для оптимизации
        stats = await asyncio.gather(
            VideoProcessing.filter(user_id=user.id).count(),
            VideoProcessing.filter(user_id=user.id).count() * config.VIDEO_PRICE,
            Referral.filter(referrer_id=user.id).count(),
            Payment.filter(user_id=user.id, description="Реферальное вознаграждение").sum("amount"),
            _get_total_deposits(user.id)
        )
        
        processed_videos, total_spent, referrals_count, referral_income, total_deposits = stats

        profile_text = (
            f"👤 <b>Профиль</b>\n\n"
            f"🆔 ID: <code>{user.id}</code>\n"
            f"📅 Регистрация: {user.registered_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"💰 Баланс: {format_rub(user.balance)}\n"
            f"💳 Всего пополнено: {format_rub(total_deposits)}\n"
            f"🎥 Обработано видео: {processed_videos}\n"
            f"💸 Всего потрачено: {format_rub(total_spent)}\n\n"
            f"👥 Приглашено друзей: {referrals_count}\n"
            f"🎁 Реферальный доход: {format_rub(referral_income or 0)}\n"
        )

        builder = InlineKeyboardBuilder()
        builder.button(text="💳 Пополнить баланс", callback_data="deposit")
        if referrals_count > 0:
            builder.button(text="👥 Мои рефералы", callback_data="my_referrals")
        builder.button(text="📤 Реферальная ссылка", callback_data="referral_link")
        builder.button(text="📊 История операций", callback_data="payment_history")
        builder.adjust(1)

        await message.answer(profile_text, reply_markup=builder.as_markup())
        
    except Exception as e:
        logger.error(f"Profile error: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка при загрузке профиля")

@router.callback_query(F.data == "deposit")
async def deposit_balance(callback: CallbackQuery, state: FSMContext):
    """Пополнение баланса с выбором суммы"""
    try:
        builder = InlineKeyboardBuilder()
        amounts = [30, 100, 300, 500, 1000]  # 30 RUB - минимальная сумма для обработки видео
        
        for amount in amounts:
            builder.button(text=f"{format_rub(amount)}", callback_data=f"deposit_{amount}")
        
        builder.button(text="🔙 Назад", callback_data="profile_back")
        builder.adjust(2)
        
        await callback.message.edit_text(
            "💰 <b>Пополнение баланса</b>\n\n"
            "Выберите сумму для пополнения:\n"
            f"Минимальная сумма для обработки видео: {format_rub(config.VIDEO_PRICE)}",
            reply_markup=builder.as_markup()
        )
    except Exception as e:
        logger.error(f"Deposit menu error: {e}")
        await callback.message.edit_text("⚠️ Ошибка при загрузке меню пополнения")
    finally:
        await callback.answer()

# Остальные обработчики (process_deposit, check_payment и т.д.) остаются без изменений

async def _get_total_deposits(user_id: int) -> float:
    """Получение общей суммы успешных пополнений"""
    result = await Payment.filter(
        user_id=user_id,
        status="paid",
        description="Пополнение баланса"
    ).sum("amount")
    return result if result else 0.0
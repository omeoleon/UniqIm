import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import config
from database.models import Payment  # Импорт модели Payment
from services.payments import payment_system

router = Router()
logger = logging.getLogger(__name__)

@router.message(Command("pay", "balance"))
async def pay_command(message: Message):
    """Обработчик команды пополнения баланса"""
    try:
        builder = InlineKeyboardBuilder()
        amounts = [100, 300, 500, 1000]  # Доступные суммы
        
        for amount in amounts:
            builder.button(
                text=f"{amount} RUB", 
                callback_data=f"deposit:{amount}"
            )
        
        builder.adjust(2, 2)
        
        balance = await payment_system.get_user_balance(message.from_user.id)
        
        await message.answer(
            f"💰 <b>Ваш баланс:</b> {balance} RUB\n\n"
            "Выберите сумму для пополнения:",
            reply_markup=builder.as_markup()
        )
    except Exception as e:
        logger.error(f"Pay command error: {e}")
        await message.answer("⚠️ Ошибка при обработке запроса")

@router.callback_query(F.data.startswith("deposit:"))
async def process_deposit(callback: CallbackQuery):
    """Обработка выбора суммы"""
    try:
        amount = int(callback.data.split(":")[1])
        payment_url, error = await payment_system.create_payment(
            user_id=callback.from_user.id,
            amount=amount,
            description="Пополнение баланса"
        )
        
        if payment_url:
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(
                    text="💳 Перейти к оплате", 
                    url=payment_url
                ),
                InlineKeyboardButton(
                    text="🔄 Проверить оплату", 
                    callback_data=f"check:{amount}"
                )
            )
            
            await callback.message.edit_text(
                f"<b>Счет на {amount} RUB</b>\n\n"
                "Ссылка действительна 24 часа\n"
                "После оплаты нажмите кнопку ниже",
                reply_markup=builder.as_markup()
            )
        else:
            await callback.answer(f"Ошибка: {error}", show_alert=True)
            
    except Exception as e:
        logger.error(f"Deposit error: {e}")
        await callback.answer("⚠️ Ошибка при создании платежа", show_alert=True)

@router.callback_query(F.data.startswith("check:"))
async def check_payment(callback: CallbackQuery):
    """Проверка статуса платежа"""
    try:
        amount = int(callback.data.split(":")[1])
        last_payment = await Payment.filter(
            user_id=callback.from_user.id
        ).order_by("-created_at").first()
        
        if not last_payment:
            await callback.answer("❌ Платеж не найден", show_alert=True)
            return
            
        payment_data, error = await payment_system.check_payment(last_payment.payment_id)
        
        if error:
            await callback.answer(f"⚠️ Ошибка: {error}", show_alert=True)
        elif payment_data["status"] == "paid":
            balance = await payment_system.get_user_balance(callback.from_user.id)
            await callback.message.edit_text(
                f"✅ Баланс пополнен на {amount} RUB\n"
                f"💰 Текущий баланс: {balance} RUB"
            )
        else:
            await callback.answer("⌛ Платеж еще не обработан", show_alert=True)
            
    except Exception as e:
        logger.error(f"Payment check error: {e}")
        await callback.answer("⚠️ Ошибка при проверке", show_alert=True)
    finally:
        await callback.answer()

__all__ = ['router']
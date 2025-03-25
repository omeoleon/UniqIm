import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.utils.markdown import hbold
from datetime import datetime  # Для работы с датами/временем

from config import config
from database.models import User, Referral
from handlers.payments import payment_system
from utils.helpers import escape_markdown

router = Router()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start с реферальной системой"""
    try:
        # Регистрация пользователя
        user, created = await User.get_or_create(
            id=message.from_user.id,
            defaults={
                'username': message.from_user.username,
                'full_name': message.from_user.full_name,
                'balance': 0.0,
                'registered_at': datetime.now()
            }
        )

        # Обработка реферальной ссылки
        if len(message.text.split()) > 1 and message.text.split()[1].startswith('ref_'):
            await handle_referral(message)

        # Обновление информации о пользователе
        if not created:
            await user.update_from_dict({
                'username': message.from_user.username,
                'full_name': message.from_user.full_name
            }).save()

        # Отправка приветственного сообщения
        await send_welcome_message(message, user, created)

    except Exception as e:
        logger.error(f"Start command error: {e}", exc_info=True)
        await message.answer("Произошла ошибка при обработке команды")

async def handle_referral(message: Message):
    """Обработка реферального приглашения"""
    referrer_id = int(message.text.split()[1].split('_')[1])
    
    # Не позволяем самоприглашение
    if referrer_id == message.from_user.id:
        return

    # Проверяем, есть ли уже такое приглашение
    if not await Referral.exists(user_id=message.from_user.id):
        # Создаем запись о реферале
        await Referral.create(
            user_id=message.from_user.id,
            referrer_id=referrer_id
        )

        # Начисляем бонус рефереру
        referrer = await User.get_or_none(id=referrer_id)
        if referrer:
            new_balance = referrer.balance + config.REFERRAL_BONUS
            await referrer.update(balance=new_balance).apply()

            # Записываем транзакцию
            await payment_system.record_payment(
                user_id=referrer_id,
                amount=config.REFERRAL_BONUS,
                description="Реферальное вознаграждение"
            )

            # Уведомляем реферера
            try:
                await message.bot.send_message(
                    referrer_id,
                    f"🎉 Вы получили {config.REFERRAL_BONUS} RUB за приглашенного друга!\n"
                    f"💰 Ваш баланс: {new_balance} RUB"
                )
            except Exception as e:
                logger.error(f"Failed to notify referrer: {e}")

async def send_welcome_message(message: Message, user: User, is_new: bool):
    """Отправка приветственного сообщения с клавиатурой"""
    # Основная клавиатура
    main_kb = ReplyKeyboardBuilder()
    main_kb.button(text="🎥 Обработать видео")
    main_kb.button(text="👤 Мой профиль")
    main_kb.button(text="🛟 Поддержка")
    main_kb.adjust(2, 1)

    # Инлайн клавиатура для новых пользователей
    inline_kb = InlineKeyboardBuilder()
    if is_new:
        inline_kb.button(text="💰 Получить стартовый бонус", callback_data="start_bonus")
        inline_kb.button(text="📤 Пригласить друзей", callback_data="invite_friends")
        inline_kb.adjust(1)

    text = (
        f"👋 Привет, {hbold(message.from_user.full_name)}!\n\n"
        "Я помогу уникализировать твои видео с помощью:\n"
        "🐊 Crocodile Room - цветокоррекция и эффекты\n"
        "🐬 Dolphin Room - шумы и анимации\n"
        "🐻 Grizzly Room - изменение скорости и обрезка\n\n"
        "Выбери действие:"
    )

    await message.answer(
        text,
        reply_markup=main_kb.as_markup(resize_keyboard=True)
    )

    if is_new:
        await message.answer(
            "🎁 Новым пользователям доступен стартовый бонус!",
            reply_markup=inline_kb.as_markup()
        )

@router.callback_query(F.data == "start_bonus")
async def give_start_bonus(callback: CallbackQuery):
    """Выдача стартового бонуса новым пользователям"""
    user = await User.get(callback.from_user.id)
    
    if user.balance > 0:
        await callback.answer("Вы уже получили бонус ранее", show_alert=True)
        return
    
    bonus_amount = config.START_BONUS
    await user.update(balance=user.balance + bonus_amount).apply()
    
    # Записываем транзакцию
    await payment_system.record_payment(
        user_id=user.id,
        amount=bonus_amount,
        description="Стартовый бонус"
    )
    
    await callback.message.edit_text(
        f"🎉 Вы получили стартовый бонус {bonus_amount} RUB!\n"
        f"💰 Ваш баланс: {bonus_amount} RUB"
    )
    await callback.answer()

@router.callback_query(F.data == "invite_friends")
async def invite_friends(callback: CallbackQuery):
    """Генерация реферальной ссылки"""
    ref_link = f"https://t.me/{config.BOT_USERNAME}?start=ref_{callback.from_user.id}"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📤 Поделиться", url=f"tg://msg_url?text={ref_link}")
    
    await callback.message.edit_text(
        f"🔗 Ваша реферальная ссылка:\n\n"
        f"<code>{ref_link}</code>\n\n"
        f"Приглашайте друзей и получайте {config.REFERRAL_BONUS} RUB за каждого!",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.message(F.text == "🎥 Обработать видео")
async def process_video_handler(message: Message):
    """Обработка нажатия кнопки обработки видео"""
    await message.answer("Для обработки видео используйте команду /process")

@router.message(F.text == "👤 Мой профиль")
async def profile_handler(message: Message):
    """Обработка нажатия кнопки профиля"""
    await message.answer("Для просмотра профиля используйте команду /profile")

@router.message(F.text == "🛟 Поддержка")
async def support_handler(message: Message):
    """Обработка нажатия кнопки поддержки"""
    await message.answer("Для связи с поддержкой используйте команду /support")
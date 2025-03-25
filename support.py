import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext

from config import config
from database.models import SupportTicket, User
from utils.states import SupportStates
from utils.helpers import escape_markdown

router = Router()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@router.message(Command("support"))
async def support_menu(message: Message):
    """Меню поддержки"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📨 Написать в поддержку", callback_data="create_ticket")
    builder.button(text="📋 Мои обращения", callback_data="my_tickets")
    builder.button(text="💡 Частые вопросы", callback_data="faq")
    builder.adjust(1)
    
    await message.answer(
        "🛠 *Служба поддержки*\n\n"
        "Выберите нужный вариант:",
        reply_markup=builder.as_markup(),
        parse_mode="MarkdownV2"
    )

@router.callback_query(F.data == "create_ticket")
async def start_ticket_creation(callback: CallbackQuery, state: FSMContext):
    """Начало создания обращения в поддержку"""
    await callback.message.edit_text(
        "✍️ *Опишите вашу проблему или вопрос*\n\n"
        "Пожалуйста, укажите:\n"
        "1\\. Что произошло?\n"
        "2\\. Когда это случилось?\n"
        "3\\. Каков ожидаемый результат?",
        parse_mode="MarkdownV2"
    )
    await state.set_state(SupportStates.waiting_for_ticket_text)
    await callback.answer()

@router.message(SupportStates.waiting_for_ticket_text)
async def process_ticket_text(message: Message, state: FSMContext):
    """Обработка текста обращения"""
    if len(message.text) < 10:
        await message.answer("Пожалуйста, опишите проблему подробнее (минимум 10 символов)")
        return
        
    ticket = await SupportTicket.create(
        user_id=message.from_user.id,
        username=message.from_user.username,
        text=message.text,
        status="open"
    )
    
    # Уведомление админов
    await notify_admins_about_new_ticket(message.bot, ticket)
    
    await message.answer(
        "✅ *Ваше обращение принято\!*\n\n"
        f"Номер обращения: `{ticket.id}`\n"
        "Мы ответим вам в ближайшее время",
        parse_mode="MarkdownV2"
    )
    await state.clear()

async def notify_admins_about_new_ticket(bot, ticket):
    """Уведомление администраторов о новом обращении"""
    admin_message = (
        "🆕 *Новое обращение в поддержку*\n\n"
        f"ID: `{ticket.id}`\n"
        f"Пользователь: @{ticket.username} \| `{ticket.user_id}`\n"
        f"Дата: {ticket.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"*Текст обращения:*\n"
        f"{escape_markdown(ticket.text)}"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Ответить", callback_data=f"reply_ticket_{ticket.id}")
    
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                admin_message,
                reply_markup=builder.as_markup(),
                parse_mode="MarkdownV2"
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")

@router.callback_query(F.data == "my_tickets")
async def show_user_tickets(callback: CallbackQuery):
    """Показать обращения пользователя"""
    tickets = await SupportTicket.filter(
        user_id=callback.from_user.id
    ).order_by("-created_at").limit(5)
    
    if not tickets:
        await callback.message.edit_text("У вас пока нет обращений в поддержку")
        await callback.answer()
        return
        
    tickets_text = "📋 *Ваши последние обращения*\n\n"
    for ticket in tickets:
        status_icon = "🟢" if ticket.status == "open" else "🔴" if ticket.status == "closed" else "🟡"
        tickets_text += (
            f"{status_icon} *Обращение #{ticket.id}*\n"
            f"Статус: {ticket.status}\n"
            f"Дата: {ticket.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="support_back")
    
    await callback.message.edit_text(
        tickets_text,
        reply_markup=builder.as_markup(),
        parse_mode="MarkdownV2"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("reply_ticket_"))
async def start_ticket_reply(callback: CallbackQuery, state: FSMContext):
    """Начало ответа на обращение (админ)"""
    ticket_id = int(callback.data.split("_")[2])
    ticket = await SupportTicket.get_or_none(id=ticket_id)
    
    if not ticket:
        await callback.answer("Обращение не найдено")
        return
        
    await state.update_data(ticket_id=ticket_id, user_id=ticket.user_id)
    await callback.message.answer(
        f"✍️ *Ответ на обращение #{ticket_id}*\n\n"
        "Введите текст ответа:",
        parse_mode="MarkdownV2"
    )
    await state.set_state(SupportStates.waiting_for_reply_text)
    await callback.answer()

@router.message(SupportStates.waiting_for_reply_text)
async def process_ticket_reply(message: Message, state: FSMContext):
    """Обработка ответа на обращение"""
    data = await state.get_data()
    ticket_id = data["ticket_id"]
    user_id = data["user_id"]
    
    try:
        # Обновляем статус тикета
        await SupportTicket.filter(id=ticket_id).update(
            status="answered",
            admin_id=message.from_user.id
        )
        
        # Отправляем ответ пользователю
        await message.bot.send_message(
            user_id,
            f"📨 *Ответ на ваше обращение #{ticket_id}*\n\n"
            f"{message.text}\n\n"
            "Если у вас остались вопросы, вы можете создать новое обращение",
            parse_mode="MarkdownV2"
        )
        
        await message.answer("✅ Ответ успешно отправлен")
    except Exception as e:
        logger.error(f"Failed to send ticket reply: {e}")
        await message.answer("Ошибка при отправке ответа")
    finally:
        await state.clear()

@router.callback_query(F.data == "faq")
async def show_faq(callback: CallbackQuery):
    """Показать частые вопросы"""
    faq_text = (
        "❓ *Часто задаваемые вопросы*\n\n"
        "1\\. *Как пополнить баланс?*\n"
        "Используйте команду /pay или кнопку в профиле\n\n"
        "2\\. *Какие методы обработки видео доступны?*\n"
        "У нас есть три метода: Crocodile, Dolphin и Grizzly Room\n\n"
        "3\\. *Максимальный размер видео?*\n"
        "Вы можете загружать видео до 1GB\n\n"
        "4\\. *Как работает реферальная система?*\n"
        "Вы получаете бонус за каждого приглашенного друга"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="support_back")
    
    await callback.message.edit_text(
        faq_text,
        reply_markup=builder.as_markup(),
        parse_mode="MarkdownV2"
    )
    await callback.answer()

@router.callback_query(F.data == "support_back")
async def back_to_support(callback: CallbackQuery):
    """Возврат в меню поддержки"""
    await support_menu(callback.message)
    await callback.answer()
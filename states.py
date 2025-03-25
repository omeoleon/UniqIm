from aiogram.fsm.state import State, StatesGroup

class PaymentStates(StatesGroup):
    """Состояния для процесса оплаты"""
    waiting_for_amount = State()      # Ожидание выбора суммы
    waiting_for_payment = State()     # Ожидание совершения платежа
    confirming_payment = State()      # Подтверждение платежа

class VideoProcessingStates(StatesGroup):
    """Состояния для обработки видео"""
    waiting_for_method = State()      # Ожидание выбора метода
    waiting_for_video = State()       # Ожидание загрузки видео

class SupportStates(StatesGroup):
    """Состояния для системы поддержки"""
    waiting_for_ticket_text = State() # Ожидание текста обращения
    waiting_for_reply_text = State()  # Ожидание текста ответа

class AdminStates(StatesGroup):
    """Состояния для админ-панели"""
    waiting_for_user_id = State()     # Для выдачи баланса
    waiting_for_amount = State()      # Для указания суммы
    waiting_for_broadcast = State()   # Для рассылки сообщений
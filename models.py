from enum import Enum
from tortoise.models import Model
from tortoise import fields, transactions
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel

# Enum классы для статусов
class PaymentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    EXPIRED = "expired"

class VideoStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class TicketStatus(str, Enum):
    OPEN = "open"
    ANSWERED = "answered"
    CLOSED = "closed"

class User(Model):
    """Модель пользователя Telegram"""
    id = fields.BigIntField(pk=True)
    username = fields.CharField(max_length=64, null=True, unique=True)
    full_name = fields.CharField(max_length=128)
    balance = fields.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    language_code = fields.CharField(max_length=8, default="ru")
    is_admin = fields.BooleanField(default=False)
    is_active = fields.BooleanField(default=True)
    registered_at = fields.DatetimeField(auto_now_add=True)
    last_active = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "users"

    async def validate_balance(self):
        """Валидация баланса (должен быть >= 0)"""
        if self.balance < Decimal('0.00'):
            raise ValueError("Balance cannot be negative")

    async def save(self, *args, **kwargs):
        await self.validate_balance()
        await super().save(*args, **kwargs)

class Payment(Model):
    """Модель платежа"""
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="payments")
    amount = fields.DecimalField(max_digits=10, decimal_places=2)
    status = fields.CharEnumField(PaymentStatus, default=PaymentStatus.PENDING)
    created_at = fields.DatetimeField(auto_now_add=True)
    paid_at = fields.DatetimeField(null=True)

    class Meta:
        table = "payments"
        ordering = ["-created_at"]

    @classmethod
    async def create_payment(
        cls,
        user_id: int,
        amount: Decimal,
        provider: str,
        description: str = None
    ) -> "Payment":
        return await cls.create(
            user_id=user_id,
            amount=amount,
            provider=provider,
            description=description
        )

class VideoProcessing(Model):
    """Модель обработки видео с улучшениями"""
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="videos", on_delete=fields.CASCADE)
    method = fields.CharField(max_length=20)  # crocodile, dolphin, grizzly
    status = fields.CharEnumField(VideoStatus, default=VideoStatus.QUEUED)
    original_file = fields.CharField(max_length=256)
    processed_file = fields.CharField(max_length=256, null=True)
    price = fields.DecimalField(max_digits=10, decimal_places=2)
    started_at = fields.DatetimeField(null=True)
    completed_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    error_message = fields.TextField(null=True)

    class Meta:
        table = "video_processing"
        ordering = ["-created_at"]

    async def start_processing(self):
        """Обновление статуса при начале обработки"""
        self.status = VideoStatus.PROCESSING
        self.started_at = datetime.now()
        await self.save()

    async def complete_processing(self, output_path: str):
        """Обновление статуса при завершении обработки"""
        self.status = VideoStatus.COMPLETED
        self.processed_file = output_path
        self.completed_at = datetime.now()
        await self.save()

class SupportTicket(Model):
    """Модель обращения в поддержку с историей сообщений"""
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="tickets", on_delete=fields.CASCADE)
    subject = fields.CharField(max_length=128)
    status = fields.CharEnumField(TicketStatus, default=TicketStatus.OPEN)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "support_tickets"
        ordering = ["-updated_at"]

class TicketMessage(Model):
    """Модель сообщений в тикете"""
    id = fields.IntField(pk=True)
    ticket = fields.ForeignKeyField("models.SupportTicket", related_name="messages", on_delete=fields.CASCADE)
    user = fields.ForeignKeyField("models.User", related_name="ticket_messages", on_delete=fields.CASCADE)
    text = fields.TextField()
    is_admin_reply = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "ticket_messages"
        ordering = ["created_at"]

class Referral(Model):
    """Модель реферальной системы с бонусами"""
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="referrals", on_delete=fields.CASCADE)
    referrer = fields.ForeignKeyField("models.User", related_name="referrers", on_delete=fields.CASCADE)
    bonus_credited = fields.BooleanField(default=False)
    bonus_amount = fields.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "referrals"
        unique_together = [("user", "referrer")]  # Уникальная пара

# Pydantic модели для API (опционально)
class UserOut(BaseModel):
    id: int
    username: Optional[str]
    full_name: str
    balance: Decimal
    is_admin: bool

    class Config:
        orm_mode = True
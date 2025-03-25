import logging
from datetime import datetime, timedelta
from aiogram import Bot

from config import config
from database.models import Referral

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.last_checked = datetime.now() - timedelta(minutes=5)

    async def check_new_referrals(self):
        """Проверка новых рефералов с кэшированием"""
        new_referrals = await Referral.filter(
            created_at__gt=self.last_checked
        ).prefetch_related("user", "referrer")
        
        if new_referrals:
            stats = {}
            for referral in new_referrals:
                if referral.referrer.id not in stats:
                    stats[referral.referrer.id] = {
                        'count': 0,
                        'referrer': referral.referrer
                    }
                stats[referral.referrer.id]['count'] += 1

            for referrer_id, data in stats.items():
                try:
                    await self.bot.send_message(
                        referrer_id,
                        f"🎉 У вас {data['count']} новых рефералов!\n"
                        f"💰 Сумма бонусов: {data['count'] * config.REFERRAL_BONUS} RUB"
                    )
                except Exception as e:
                    logger.error(f"Referral notification failed: {e}")

        self.last_checked = datetime.now()
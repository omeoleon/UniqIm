from .start import router as start_router
from handlers.profile import router as profile_router
from .process_video import router as process_video_router
from .support import router as support_router
from .admin import router as admin_router
from handlers.payments import router as payments_router

# Собираем все роутеры в один список для удобного импорта
routers = [
    start_router,
    profile_router,
    process_video_router,
    support_router,
    admin_router,
    payments_router,
]

__all__ = [
    'start_router',
    'profile_router',
    'process_video_router',
    'support_router',
    'admin_router',
    'payments_router',
    'routers',  # Основной список для использования в main.py
]
from datetime import timedelta

def format_timedelta(td: timedelta) -> str:
    """Форматирует временной интервал в ЧЧ:ММ:СС"""
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"

def escape_markdown(text: str) -> str:
    """Экранирует Markdown-символы для Telegram"""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{char}' if char in escape_chars else char for char in text)

def format_bytes(size: int) -> str:
    """Конвертирует байты в KB/MB/GB"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"

def format_rub(amount: float) -> str:
    """Форматирует рубли (1 500 ₽)"""
    return f"{amount:,.0f} ₽".replace(",", " ")
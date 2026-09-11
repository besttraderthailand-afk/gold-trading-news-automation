"""
Utility helpers
"""
from datetime import datetime
import pytz
from config.settings import get_settings


def now_ict() -> datetime:
    settings = get_settings()
    return datetime.now(pytz.timezone(settings.timezone))


def format_time_ict(dt: datetime) -> str:
    settings = get_settings()
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    return dt.astimezone(pytz.timezone(settings.timezone)).strftime("%H:%M")

"""
utils.py
--------
Вспомогательные функции для форматирования дат и времени.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

MOSCOW_TZ = ZoneInfo("Europe/Moscow")


def now_moscow() -> datetime:
    """Текущее время в московской таймзоне."""
    return datetime.now(MOSCOW_TZ)


def format_hm(dt: datetime) -> str:
    """Форматирует время как ЧЧ:ММ."""
    return dt.strftime("%H:%M")


RU_MONTHS = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}

RU_WEEKDAYS_FULL = {
    0: "Понедельник", 1: "Вторник", 2: "Среда", 3: "Четверг",
    4: "Пятница", 5: "Суббота", 6: "Воскресенье",
}

RU_WEEKDAYS_SHORT = {
    0: "пн", 1: "вт", 2: "ср", 3: "чт",
    4: "пт", 5: "сб", 6: "вс",
}


def format_ru_date(dt: date) -> str:
    """Форматирует дату в виде 'Четверг, 24 сентября'."""
    weekday = RU_WEEKDAYS_FULL[dt.weekday()]
    return f"{weekday}, {dt.day} {RU_MONTHS[dt.month]}"


def format_ru_date_short(dt: date) -> str:
    """Форматирует дату в виде '24.09 (чт)'."""
    weekday = RU_WEEKDAYS_SHORT[dt.weekday()]
    return f"{dt.day:02d}.{dt.month:02d} ({weekday})"

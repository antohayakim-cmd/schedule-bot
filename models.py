"""
models.py
---------
Модель данных для занятия в расписании.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Lesson:
    """Одно занятие в расписании."""

    id: str
    subject: str
    teacher: str
    lesson_type: str
    building: str
    room: str
    start_datetime: datetime
    end_datetime: datetime
    is_online: bool = False
    url: str = ""

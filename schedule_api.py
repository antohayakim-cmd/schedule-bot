"""
schedule_api.py
---------------
Запросы к RUZ API ННГУ для получения расписания.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

import httpx

from parser import parse_lessons
from models import Lesson

log = logging.getLogger(__name__)


async def fetch_schedule_range(
    client: httpx.AsyncClient,
    ruz_base_url: str,
    group_id: str,
    start: date,
    finish: date,
) -> list[Lesson]:
    """Запрашивает расписание группы за диапазон дат [start, finish]."""
    if finish < start:
        raise ValueError("Конец диапазона раньше начала")
    url = f"{ruz_base_url.rstrip('/')}/schedule/group/{group_id}"
    
    log.info("Запрашиваю расписание группы %s с %s по %s", group_id, start, finish)
    
    response = await client.get(
        url,
        params={
            "start": start.isoformat(),
            "finish": finish.isoformat(),
            "lng": 1,
        },
        timeout=25.0,
        headers={"User-Agent": "ScheduleBot/1.0"},
    )
    response.raise_for_status()
    
    raw = response.json()
    if not isinstance(raw, list):
        raise RuntimeError(
            f"Неожиданный формат ответа RUZ API (ожидался список): {type(raw)}"
        )
    
    return parse_lessons(raw)


async def get_schedule_for_date(
    client: httpx.AsyncClient,
    ruz_base_url: str,
    group_id: str,
    target_date: date,
) -> list[Lesson]:
    """Получает расписание на конкретный день."""
    lessons = await fetch_schedule_range(client, ruz_base_url, group_id, target_date, target_date)
    return [ls for ls in lessons if ls.start_datetime.date() == target_date]


async def get_schedule_for_week(
    client: httpx.AsyncClient,
    ruz_base_url: str,
    group_id: str,
    start_date: date,
) -> dict[date, list[Lesson]]:
    """
    Получает расписание на неделю начиная с start_date.
    Возвращает словарь {дата: список занятий}.
    """
    end_date = start_date + timedelta(days=6)
    lessons = await fetch_schedule_range(client, ruz_base_url, group_id, start_date, end_date)
    
    # Группируем по датам
    schedule_by_date: dict[date, list[Lesson]] = {}
    for lesson in lessons:
        lesson_date = lesson.start_datetime.date()
        if lesson_date not in schedule_by_date:
            schedule_by_date[lesson_date] = []
        schedule_by_date[lesson_date].append(lesson)
    
    return schedule_by_date

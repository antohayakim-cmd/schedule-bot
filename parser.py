"""
parser.py
---------
Разбор ответа RUZ API (портал ННГУ) в список объектов Lesson.
"""

from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from models import Lesson

MOSCOW_TZ = ZoneInfo("Europe/Moscow")

log = logging.getLogger(__name__)

ONLINE_BUILDING_MARKERS = ("виртуальн", "онлайн", "online", "дистанц", "эиос")
ONLINE_ROOM_MARKERS = ("д.а", "дист", "онлайн", "online", "эиос", "zoom", "webinar")


def _first_present(item: dict, *keys: str, default: str = "") -> str:
    """Возвращает первое непустое значение по списку ключей."""
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return str(value)
    return default


def _is_online_lesson(raw: dict, building: str, room: str, url: str) -> bool:
    """Определяет, проходит ли занятие онлайн (дистанционно)."""
    b_low = building.strip().lower()
    r_low = room.strip().lower()
    if any(marker in b_low for marker in ONLINE_BUILDING_MARKERS):
        return True
    if any(marker in r_low for marker in ONLINE_ROOM_MARKERS):
        return True
    if raw.get("buildingOid") == 1 or raw.get("auditoriumOid") == 118:
        return True
    if url:
        return True
    return False


def _parse_datetime(raw_date: str, raw_time: str) -> datetime:
    """Парсит дату и время из строк RUZ API."""
    raw_date = raw_date.strip()
    raw_time = raw_time.strip()
    
    date_formats = ("%Y.%m.%d", "%Y-%m-%d", "%d.%m.%Y")
    parsed_date = None
    
    for fmt in date_formats:
        try:
            parsed_date = datetime.strptime(raw_date, fmt)
            break
        except ValueError:
            continue
    
    if parsed_date is None:
        raise ValueError(f"Не удалось разобрать дату: {raw_date!r}")

    try:
        hour, minute = (int(part) for part in raw_time.split(":")[:2])
    except (ValueError, IndexError) as exc:
        raise ValueError(f"Не удалось разобрать время: {raw_time!r}") from exc

    return parsed_date.replace(
        hour=hour, minute=minute, second=0, microsecond=0, tzinfo=MOSCOW_TZ
    )


def parse_lessons(raw_items: list[dict]) -> list[Lesson]:
    """
    Превращает JSON-ответ RUZ API в список Lesson.
    Некорректные элементы пропускаются с предупреждением.
    """
    lessons: list[Lesson] = []

    for raw in raw_items:
        try:
            if not isinstance(raw, dict):
                raise TypeError("Элемент расписания должен быть объектом")
            lesson_id = _first_present(raw, "id", "lessonOid", "oid", default="0")
            subject = _first_present(raw, "discipline", "subject", "disciplineName")
            teacher = _first_present(
                raw, "lecturer", "teacher", "lecturer_title", "fio"
            )
            lesson_type = _first_present(
                raw, "kindOfWork", "lessonType", "type", default="Занятие"
            )
            building = _first_present(raw, "building", "buildingNumber", "corpus")
            room = _first_present(raw, "auditorium", "room", "aud")
            url = _first_present(raw, "url1", "url2", "url").strip()

            raw_date = _first_present(raw, "date", "Date")
            begin_time = _first_present(raw, "beginLesson", "startTime", "begin")
            end_time = _first_present(raw, "endLesson", "endTime", "end")

            start_dt = _parse_datetime(raw_date, begin_time)
            end_dt = _parse_datetime(raw_date, end_time)
            is_online = _is_online_lesson(raw, building, room, url)

            lessons.append(
                Lesson(
                    id=str(lesson_id),
                    subject=subject or "Без названия",
                    teacher=teacher or "Не указан",
                    lesson_type=lesson_type,
                    building=str(building) if building else "?",
                    room=room or "?",
                    start_datetime=start_dt,
                    end_datetime=end_dt,
                    is_online=is_online,
                    url=url,
                )
            )
        except (ValueError, KeyError, TypeError) as exc:
            log.warning("Пропускаю занятие, не удалось разобрать: %s (%s)", raw, exc)
            continue

    if raw_items and not lessons:
        raise ValueError("API вернул занятия, но ни одно не удалось разобрать")
    lessons.sort(key=lambda lesson: lesson.start_datetime)
    return lessons

import unittest
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from telegram import Message, Update
from telegram.ext import Application

from bot import (button_callback, format_schedule, get_weekday_buttons,
                 schedule_handler, split_message)
from config import Config
from parser import parse_lessons
from schedule_api import fetch_schedule_range
from utils import MOSCOW_TZ
from datetime import datetime

RAW = {"date": "2026.09.24", "beginLesson": "10:50", "endLesson": "12:20",
       "discipline": "Математика_*", "lecturer": "Иванов", "auditorium": "201"}


class CalendarTests(unittest.TestCase):
    def test_buttons_every_weekday_and_year_boundary(self):
        for offset in range(14):
            today = date(2026, 12, 21) + timedelta(days=offset)
            keyboard = get_weekday_buttons(today)
            dates = [date.fromisoformat(b.callback_data[4:])
                     for row in keyboard.inline_keyboard for b in row
                     if b.callback_data.startswith("day:")]
            self.assertEqual(dates, [today + timedelta(days=n)
                                    for n in range(2, 7)])

    def test_empty_day_uses_requested_date(self):
        self.assertIn("24 сентября", format_schedule([], date(2026, 9, 24)))
        self.assertIn("Занятий нет", format_schedule([], date(2026, 9, 24)))

    def test_parser_and_sort(self):
        lessons = parse_lessons([dict(RAW, beginLesson="14:00"), RAW, None])
        self.assertEqual(lessons[0].start_datetime.hour, 10)
        self.assertEqual(lessons[0].start_datetime.tzinfo, MOSCOW_TZ)
        self.assertIn("Математика_*", format_schedule(lessons, date(2026, 9, 24)))
        with self.assertRaises(ValueError):
            parse_lessons([{"date": "bad"}])

    def test_long_message(self):
        chunks = split_message("Предмет\n" * 2500)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk.encode("utf-16-le")) // 2 <= 4096 for chunk in chunks))


class IntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.requests = []
        def respond(request):
            self.requests.append(request)
            return httpx.Response(200, json=[RAW])
        self.client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        self.context = SimpleNamespace(bot_data={
            "config": Config("dummy", "50793", "https://example.test/ruzapi"),
            "client": self.client,
        })

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_request_contract(self):
        day = date(2026, 9, 24)
        lessons = await fetch_schedule_range(self.client, "https://example.test/ruzapi/", "50793", day, day)
        self.assertEqual(len(lessons), 1)
        self.assertEqual(self.requests[0].url.path, "/ruzapi/schedule/group/50793")
        self.assertEqual(dict(self.requests[0].url.params),
                         {"start": "2026-09-24", "finish": "2026-09-24", "lng": "1"})

    async def test_text_request_today_tomorrow(self):
        message = SimpleNamespace(reply_text=AsyncMock())
        status = SimpleNamespace(edit_text=AsyncMock())
        message.reply_text.return_value = status
        with patch("bot.now_moscow", return_value=datetime(2026, 9, 24, tzinfo=MOSCOW_TZ)):
            await schedule_handler(SimpleNamespace(effective_message=message), self.context)
        text = status.edit_text.call_args.args[0]
        self.assertIn("СЕГОДНЯ", text)
        self.assertIn("ЗАВТРА", text)
        self.assertIn("25 сентября", text)
        self.assertEqual(len(self.requests), 1)

    async def test_button_selected_date(self):
        message = SimpleNamespace(edit_text=AsyncMock(), reply_text=AsyncMock())
        query = SimpleNamespace(message=message, data="day:2026-09-26", answer=AsyncMock())
        with patch("bot.now_moscow", return_value=datetime(2026, 9, 24, tzinfo=MOSCOW_TZ)):
            await button_callback(SimpleNamespace(callback_query=query), self.context)
        self.assertIn("26 сентября", message.edit_text.call_args.args[0])
        self.assertIn("Занятий нет", message.edit_text.call_args.args[0])
        self.assertEqual(self.requests[0].url.params["start"], "2026-09-26")

    async def test_api_failure_keeps_keyboard(self):
        def fail(request):
            return httpx.Response(503)
        async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as client:
            self.context.bot_data["client"] = client
            message = SimpleNamespace(reply_text=AsyncMock())
            status = SimpleNamespace(edit_text=AsyncMock())
            message.reply_text.return_value = status
            await schedule_handler(SimpleNamespace(effective_message=message), self.context)
            self.assertIn("Не удалось", status.edit_text.call_args.args[0])
            self.assertIsNotNone(status.edit_text.call_args.kwargs["reply_markup"])

    async def test_text_filter_without_slash(self):
        # Проверяем тот же фильтр, который зарегистрирован в main.
        from telegram.ext import filters
        text_filter = filters.TEXT & ~filters.COMMAND & filters.Regex(r"(?i)^\s*расписание\s*$")
        app = Application.builder().token("123:dummy").build()
        for text in ["расписание", " РАСПИСАНИЕ "]:
            update = Update.de_json({"update_id": 1, "message": {
                "message_id": 1, "date": 0, "chat": {"id": 1, "type": "private"}, "text": text}}, app.bot)
            self.assertTrue(text_filter.check_update(update))

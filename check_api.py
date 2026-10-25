"""Проверка живого RUZ API без токена Telegram: python check_api.py."""
import asyncio
from datetime import timedelta

import httpx

from schedule_api import fetch_schedule_range
from utils import now_moscow


async def main():
    today = now_moscow().date()
    async with httpx.AsyncClient(follow_redirects=True) as client:
        lessons = await fetch_schedule_range(
            client, "https://portal.unn.ru/ruzapi", "50793", today, today + timedelta(days=1)
        )
    print(f"API OK: {today} / {today + timedelta(days=1)}; lessons: {len(lessons)}")


if __name__ == "__main__":
    asyncio.run(main())

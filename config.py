"""
config.py
---------
Конфигурация бота из переменных окружения.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")


def _get_env(name: str, default: str | None = None, required: bool = False) -> str:
    value = os.environ.get(name, default)
    if required and not value:
        raise RuntimeError(
            f"Обязательная переменная окружения {name} не задана. "
            f"Проверь файл .env."
        )
    return value or ""


@dataclass(frozen=True)
class Config:
    """Конфигурация бота."""
    
    # Telegram
    telegram_bot_token: str
    
    # Расписание ННГУ
    unn_group_id: str
    ruz_base_url: str


def load_config() -> Config:
    """Загружает конфигурацию из переменных окружения."""
    token = (
        os.environ.get("TELEGRAM_BOT_TOKEN")
        or os.environ.get("BOT_TOKEN")
        or os.environ.get("API_TOKEN")
        or ""
    ).strip()
    if not token:
        raise RuntimeError(
            "Токен бота не задан (ожидается TELEGRAM_BOT_TOKEN или BOT_TOKEN)."
        )
    return Config(
        telegram_bot_token=token,
        unn_group_id=_get_env("UNN_GROUP_ID", default="50793"),
        ruz_base_url=_get_env(
            "RUZ_BASE_URL", default="https://portal.unn.ru/ruzapi"
        ),
    )

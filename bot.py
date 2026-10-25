"""Telegram-бот расписания ННГУ. Запуск: python bot.py."""
from __future__ import annotations

import logging
from datetime import date, timedelta

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from config import load_config
from models import Lesson
from schedule_api import fetch_schedule_range, get_schedule_for_date
from utils import format_hm, format_ru_date, format_ru_date_short, now_moscow

logger = logging.getLogger(__name__)
ERROR_TEXT = "Не удалось загрузить расписание. Попробуй ещё раз: расписание."


def format_lesson(lesson: Lesson) -> str:
    return (
        f"📚 {lesson.subject}\n"
        f"🕐 {format_hm(lesson.start_datetime)}–{format_hm(lesson.end_datetime)}\n"
        f"👤 {lesson.teacher}\n"
        f"🏛 Корпус {lesson.building}, аудитория {lesson.room}\n"
        f"📝 {lesson.lesson_type}"
    )


def format_schedule(lessons: list[Lesson], day_date: date) -> str:
    header = f"📅 {format_ru_date(day_date)}\n\n"
    return header + ("\n\n".join(
        f"{i}. {format_lesson(lesson)}" for i, lesson in enumerate(lessons, 1)
    ) if lessons else "✨ Занятий нет")


def get_weekday_buttons(current_date: date) -> InlineKeyboardMarkup:
    # Сегодня и завтра уже показаны; в кнопки выводим следующие 5 будущих дней (на неделю вперёд).
    buttons = [InlineKeyboardButton(
        format_ru_date_short(current_date + timedelta(days=offset)),
        callback_data=f"day:{(current_date + timedelta(days=offset)).isoformat()}",
    ) for offset in range(2, 7)]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton("Сегодня и завтра / обновить", callback_data="overview")])
    return InlineKeyboardMarkup(rows)


def split_message(text: str, limit: int = 1900) -> list[str]:
    # Запас до лимита Telegram (4096), в том числе для emoji в UTF-16.
    chunks = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit + 1)
        if cut <= 0:
            cut = limit
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    if text:
        chunks.append(text)
    return chunks


async def send_result(message, text: str, keyboard, *, edit: bool = False) -> None:
    chunks = split_message(text)
    for index, chunk in enumerate(chunks):
        markup = keyboard if index == len(chunks) - 1 else None
        if edit and index == 0:
            try:
                await message.edit_text(chunk, reply_markup=markup)
            except BadRequest as exc:
                if "message is not modified" not in str(exc).lower():
                    raise
        else:
            await message.reply_text(chunk, reply_markup=markup)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(
            "👋 Привет! Отправь слово «расписание» без слеша.\n"
            f"Покажу занятия группы {context.bot_data['config'].unn_group_id} на сегодня и завтра, а под ними — "
            "кнопки со следующими днями недели. Время московское.",
            reply_markup=ReplyKeyboardMarkup([["расписание"]], resize_keyboard=True),
        )


async def overview(context: ContextTypes.DEFAULT_TYPE, today: date) -> str:
    cfg = context.bot_data["config"]
    tomorrow = today + timedelta(days=1)
    lessons = await fetch_schedule_range(
        context.bot_data["client"], cfg.ruz_base_url, cfg.unn_group_id, today, tomorrow
    )
    return "📌 СЕГОДНЯ\n\n" + format_schedule(
        [lesson for lesson in lessons if lesson.start_datetime.date() == today], today
    ) + "\n\n────────────\n\n📌 ЗАВТРА\n\n" + format_schedule(
        [lesson for lesson in lessons if lesson.start_datetime.date() == tomorrow], tomorrow
    )


async def schedule_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message:
        return
    status = await message.reply_text("⏳ Загружаю расписание…")
    today = now_moscow().date()
    try:
        text = await overview(context, today)
    except (httpx.HTTPError, ValueError, RuntimeError):
        logger.warning("Не удалось получить расписание", exc_info=True)
        text = ERROR_TEXT
    await send_result(status, text, get_weekday_buttons(today), edit=True)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message:
        return
    await query.answer()
    today = now_moscow().date()
    try:
        if query.data == "overview":
            text = await overview(context, today)
        else:
            target_date = date.fromisoformat(query.data.removeprefix("day:"))
            max_date = today + timedelta(days=6)
            if not today <= target_date <= max_date:
                await query.message.reply_text("Эта кнопка устарела. Отправь «расписание» для новых дат.")
                return
            cfg = context.bot_data["config"]
            lessons = await get_schedule_for_date(
                context.bot_data["client"], cfg.ruz_base_url, cfg.unn_group_id, target_date
            )
            text = format_schedule(lessons, target_date)
    except (httpx.HTTPError, ValueError, RuntimeError):
        logger.warning("Не удалось получить расписание по кнопке", exc_info=True)
        text = ERROR_TEXT
    await send_result(query.message, text, get_weekday_buttons(today), edit=True)


async def post_init(application: Application) -> None:
    application.bot_data["client"] = httpx.AsyncClient(follow_redirects=True)


async def post_shutdown(application: Application) -> None:
    client = application.bot_data.get("client")
    if client:
        await client.aclose()


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Ошибка обработки Telegram update", exc_info=context.error)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # HTTP-журнал Telegram содержит URL с токеном бота.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    cfg = load_config()
    application = (Application.builder().token(cfg.telegram_bot_token)
                   .post_init(post_init).post_shutdown(post_shutdown).build())
    application.bot_data["config"] = cfg
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(r"(?i)^\s*расписание\s*$"), schedule_handler
    ))
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(r"(?i)^\s*(старт|помощь)\s*$"), start_command
    ))
    application.add_handler(CallbackQueryHandler(button_callback, pattern=r"^(overview|day:\d{4}-\d{2}-\d{2})$"))
    application.add_error_handler(on_error)
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()

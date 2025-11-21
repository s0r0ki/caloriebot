import os
import re
import sqlite3
import logging
from datetime import datetime

import pytz
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command, CommandStart

# ---------- НАСТРОЙКИ ----------

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Не задан BOT_TOKEN в переменных окружения")

# Таймзона (по умолчанию Ереван)
TIMEZONE_NAME = os.getenv("TZ", "Asia/Yerevan")
TIMEZONE = pytz.timezone(TIMEZONE_NAME)

DB_PATH = "calories.db"
DEFAULT_DAILY_LIMIT = 2000  # если лимит не задан явно

# ---------- ЛОГИ ----------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- БАЗА ДАННЫХ ----------


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # калории по дням
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS entries (
            user_id INTEGER,
            date TEXT,
            calories INTEGER,
            PRIMARY KEY (user_id, date)
        )
        """
    )

    # дневные лимиты
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS limits (
            user_id INTEGER PRIMARY KEY,
            daily_limit INTEGER
        )
        """
    )

    conn.commit()
    conn.close()


def get_today_date_str() -> str:
    now = datetime.now(TIMEZONE)
    return now.date().isoformat()


def add_calories(user_id: int, calories: int) -> int:
    """Добавить калории за сегодня, вернуть итог за день."""
    date_str = get_today_date_str()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO entries (user_id, date, calories)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, date) DO UPDATE SET
            calories = calories + excluded.calories
        """,
        (user_id, date_str, calories),
    )
    conn.commit()

    cur.execute(
        "SELECT calories FROM entries WHERE user_id = ? AND date = ?",
        (user_id, date_str),
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else calories


def get_today_calories(user_id: int) -> int:
    date_str = get_today_date_str()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT calories FROM entries WHERE user_id = ? AND date = ?",
        (user_id, date_str),
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0


def reset_today(user_id: int):
    date_str = get_today_date_str()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM entries WHERE user_id = ? AND date = ?",
        (user_id, date_str),
    )
    conn.commit()
    conn.close()


def set_limit_for_user(target_user_id: int, daily_limit: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO limits (user_id, daily_limit)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            daily_limit = excluded.daily_limit
        """,
        (target_user_id, daily_limit),
    )
    conn.commit()
    conn.close()


def get_limit_for_user(user_id: int) -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT daily_limit FROM limits WHERE user_id = ?",
        (user_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else DEFAULT_DAILY_LIMIT


# ---------- ПАРСИНГ КАЛОРИЙ ----------


def parse_calories_from_text(text: str) -> int | None:
    """
    Примеры:
    "450" -> 450
    "85 на 2.7" -> round(85 * 2.7)
    "85 * 2.7" -> round(85 * 2.7)
    "100 + 50" -> 150
    """
    clean = text.lower().replace(",", ".")
    numbers = re.findall(r"\d+(?:\.\d+)?", clean)
    if not numbers:
        return None

    nums = [float(x) for x in numbers]

    # если есть "на", "x" или "*" — считаем произведение
    if any(s in clean for s in [" на ", " x ", " * ", "×"]):
        val = 1.0
        for n in nums:
            val *= n
    # если есть "+" — считаем сумму
    elif "+" in clean:
        val = sum(nums)
    else:
        # по умолчанию первая цифра
        val = nums[0]

    return int(round(val))


# ---------- TELEGRAM-БОТ ----------

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)


@router.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    limit_ = get_limit_for_user(user_id)

    await message.answer(
        "Привет! Я считаю калории за день.\n\n"
        "Просто отправляй мне число (или что-то вроде `85 на 2.7`), "
        "а я буду копить и говорить, сколько уже съел.\n\n"
        f"Текущий дневной лимит: {limit_} калорий.\n\n"
        "Команды:\n"
        "/limit 2000 — установить свой дневной лимит\n"
        "/limit_for <user_id> 1800 — поставить лимит другому пользователю\n"
        "/today — сколько уже съел сегодня\n"
        "/reset — обнулить сегодняшний день",
        parse_mode="Markdown",
    )


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await cmd_start(message)


@router.message(Command("limit"))
async def cmd_limit(message: types.Message):
    """
    /limit 2000 — задать себе
    """
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Формат: /limit 2000")
        return

    try:
        value = int(parts[1])
        if value <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Лимит должен быть положительным числом, например: /limit 1800")
        return

    user_id = message.from_user.id
    set_limit_for_user(user_id, value)
    await message.answer(f"Твой дневной лимит теперь {value} калорий.")


@router.message(Command("limit_for"))
async def cmd_limit_for(message: types.Message):
    """
    /limit_for <user_id> <калории>
    Например: /limit_for 123456789 1800
    """
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("Формат: /limit_for <user_id> <калории>")
        return

    try:
        target_id = int(parts[1])
        value = int(parts[2])
        if value <= 0:
            raise ValueError
    except ValueError:
        await message.answer("user_id и лимит должны быть числами. Пример: /limit_for 123456789 1800")
        return

    set_limit_for_user(target_id, value)
    await message.answer(f"Лимит {value} калорий установлен для user_id={target_id}.")


@router.message(Command("today"))
async def cmd_today(message: types.Message):
    user_id = message.from_user.id
    used = get_today_calories(user_id)
    limit_ = get_limit_for_user(user_id)
    left = limit_ - used

    if left >= 0:
        text = (
            f"Сегодня ты уже съел {used} калорий.\n"
            f"Лимит: {limit_}. Осталось: {left}."
        )
    else:
        text = (
            f"Сегодня ты съел {used} калорий.\n"
            f"Лимит: {limit_}. Перебор: {abs(left)}."
        )
    await message.answer(text)


@router.message(Command("reset"))
async def cmd_reset(message: types.Message):
    user_id = message.from_user.id
    reset_today(user_id)
    await message.answer("Сегодняшние калории обнулены.")


@router.message(F.text)
async def handle_calorie_input(message: types.Message):
    # игнорируем команды, на всякий случай
    if message.text.startswith("/"):
        return

    cals = parse_calories_from_text(message.text)
    if cals is None or cals <= 0:
        await message.answer(
            "Не нашёл калории в сообщении. Напиши, например: `450` или `85 на 2.7`.",
            parse_mode="Markdown",
        )
        return

    user_id = message.from_user.id
    total = add_calories(user_id, cals)
    limit_ = get_limit_for_user(user_id)
    left = limit_ - total

    if left >= 0:
        text = (
            f"+{cals} калорий.\n"
            f"За сегодня: {total} из {limit_}. Осталось: {left}."
        )
    else:
        text = (
            f"+{cals} калорий.\n"
            f"За сегодня: {total} при лимите {limit_}. Перебор: {abs(left)}."
        )

    await message.answer(text)


# ---------- MAIN ----------

async def main():
    init_db()
    logger.info("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

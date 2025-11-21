import os
import json
import random
from datetime import datetime

import pytz
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.dispatcher.filters import Command

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

DATA_FILE = "data.json"
DEFAULT_LIMIT = 2000
TZ = pytz.timezone("Asia/Yerevan")  # можно сменить при желании

# ---------- ХРАНИЛИЩЕ ДАННЫХ ----------

user_limits = {}         # { user_id: limit }
daily_calories = {}      # { date_str: { user_id: used } }


def load_data():
    """Читаем лимиты и калории из файла при старте."""
    global user_limits, daily_calories
    if not os.path.exists(DATA_FILE):
        user_limits = {}
        daily_calories = {}
        return

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        # если файл побился — начинаем с чистого листа
        user_limits = {}
        daily_calories = {}
        return

    limits_raw = raw.get("limits", {})
    daily_raw = raw.get("daily", {})

    user_limits = {int(uid): int(limit) for uid, limit in limits_raw.items()}

    daily_calories = {}
    for date_str, per_day in daily_raw.items():
        daily_calories[date_str] = {int(uid): int(val) for uid, val in per_day.items()}


def save_data():
    """Сохраняем лимиты и калории в файл после каждого изменения."""
    raw = {
        "limits": {str(uid): limit for uid, limit in user_limits.items()},
        "daily": {
            date_str: {str(uid): val for uid, val in per_day.items()}
            for date_str, per_day in daily_calories.items()
        },
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False)


def today_key():
    now = datetime.now(TZ)
    return now.strftime("%Y-%m-%d")


def get_user_limit(user_id: int) -> int:
    return user_limits.get(user_id, DEFAULT_LIMIT)


def add_calories(user_id: int, amount: int) -> tuple[int, int]:
    """
    Добавляет amount к сегодняшним калориям пользователя.
    Возвращает (использовано, осталось).
    """
    date_str = today_key()

    if date_str not in daily_calories:
        daily_calories[date_str] = {}

    used = daily_calories[date_str].get(user_id, 0)
    used += amount
    daily_calories[date_str][user_id] = used

    limit = get_user_limit(user_id)
    remaining = limit - used
    return used, remaining


def reset_today_for_user(user_id: int):
    """Сбросить только сегодняшний день для пользователя."""
    date_str = today_key()
    if date_str in daily_calories and user_id in daily_calories[date_str]:
        del daily_calories[date_str][user_id]
        if not daily_calories[date_str]:
            del daily_calories[date_str]


# ---------- РЕАКЦИИ ----------

def pick_reaction_by_meal(cal: int) -> str:
    c = cal
    if c <= 50:
        pool = [
            "Это что, калории или опечатка?",
            "Микро-перекус для совести.",
            "Организм даже не заметил.",
            "Так ты больше потратил, печатая сообщение.",
            "Диета не поняла, было что-то или нет.",
        ]
    elif c <= 150:
        pool = [
            "Лёгкий заход, как раз разогреться.",
            "Чисто разминка для желудка.",
            "Так скромно, будто ты ангел.",
            "Перекус уровня «я почти молодец».",
            "Желудок сказал «ок, продолжай».",
        ]
    elif c <= 300:
        pool = [
            "Нормальный такой перекус, без драмы.",
            "Середнячок — ни стыдно, ни гордиться.",
            "Так ест человек, который ещё контролирует ситуацию.",
            "Баланс между вкусно и разумно.",
            "Плотненько, но без фанатизма.",
        ]
    elif c <= 600:
        pool = [
            "Плотно сел, плотнее жить будешь.",
            "Желудок аплодирует стоя.",
            "Это уже серьёзный приём, а не «перекусик».",
            "Так едят люди с планом.",
            "Организм такой: «Спасибо, можно запомнить».",
        ]
    elif c <= 900:
        pool = [
            "Вот это ты зарядился.",
            "Желудок только что подписал контракт на работу.",
            "Калории сейчас такие: «мы в деле».",
            "Порция уровня «живу один раз».",
            "Диета тихо вышла из чата.",
        ]
    else:
        pool = [
            "Это было блюдо или босс-рейд?",
            "Калории сейчас оформляют ипотеку в твоём теле.",
            "Так едят перед зимней спячкой.",
            "С таким приёмом пищи можно еду на завтра отменять.",
            "Желудок попросил автограф.",
        ]
    return random.choice(pool)


def pick_reaction_by_remaining(remaining: int, limit: int) -> str:
    used = limit - remaining
    if remaining <= 0:
        pool = [
            "Лимит официально закончен, поздравляю… или сочувствую.",
            "Всё, калорийный кредит, дальше в долг.",
            "На сегодня ты уже в овердрафте.",
            "Диета хлопнула дверью и ушла.",
            "Счётчик сказал: «я устал, я ухожу».",
        ]
    else:
        fill = used / limit
        if fill < 0.25:
            pool = [
                "Запас дикий, можно жить спокойно.",
                "Ты ещё даже не начал, по сути.",
                "Лимит смотрит на тебя с уважением.",
                "Диета тобой довольна, можешь хрустеть салатиком.",
                "Калорий почти нет, одни амбиции.",
            ]
        elif fill < 0.5:
            pool = [
                "Уже что-то поел, но без паники.",
                "Экватор ещё впереди, можно не нервничать.",
                "Лимит такой: «я чувствую лёгкий тик, но пока норм».",
                "Контроль есть, и это видно.",
                "Серединка на половинку — живём.",
            ]
        elif fill < 0.75:
            pool = [
                "Вот сейчас уже начинается интересное.",
                "Лимит слегка напрягся, но держится.",
                "Ещё ок, но вторая половина дня смотрит с подозрением.",
                "Диета нервно закурила, но пока не ушла.",
                "До края ещё есть место, но не разгоняйся.",
            ]
        else:
            pool = [
                "Очень аккуратно, ты почти у края.",
                "Ещё один такой заход — и всё.",
                "Лимит уже собирает чемоданы.",
                "Диета висит на занавеске и кричит.",
                "Калорийный потолок уже стучит по голове.",
            ]
    return random.choice(pool)


def build_reply_text(cal: int, remaining: int, limit: int) -> str:
    # случайно выбираем тип реакции
    if random.choice([True, False]):
        react = pick_reaction_by_meal(cal)
    else:
        react = pick_reaction_by_remaining(remaining, limit)

    sign = "-" if cal >= 0 else "+"
    cal_abs = abs(cal)
    return f"{sign}{cal_abs} ккал. Осталось {max(remaining, 0)}. {react}"


# ---------- ХЕНДЛЕРЫ ----------

@dp.message_handler(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.full_name

    if user_id not in user_limits:
        user_limits[user_id] = DEFAULT_LIMIT
        save_data()

    await message.answer(
        f"Привет, {username}!\n"
        f"Я считаю калории. Твой лимит: {user_limits[user_id]} ккал в день.\n\n"
        f"Просто пиши мне вроде: <code>350</code>, <code>800 ккал</code> и т.п.\n"
        f"Команды:\n"
        f"/setlimit 2200 — изменить лимит\n"
        f"/today — показать итоги за сегодня\n"
        f"/reset_today — обнулить сегодняшний день"
    )


@dp.message_handler(Command("setlimit"))
async def cmd_setlimit(message: types.Message):
    user_id = message.from_user.id
    parts = message.text.split()

    if len(parts) < 2:
        await message.answer("Напиши так: /setlimit 2000")
        return

    try:
        new_limit = int(parts[1])
    except ValueError:
        await message.answer("Лимит должен быть числом, например: /setlimit 1800")
        return

    if new_limit <= 0:
        await message.answer("Лимит должен быть положительным числом.")
        return

    user_limits[user_id] = new_limit
    save_data()

    username = message.from_user.username or message.from_user.full_name
    await message.answer(f"Лимит для {username} установлен: {new_limit} ккал.")


@dp.message_handler(Command("today"))
async def cmd_today(message: types.Message):
    user_id = message.from_user.id
    date_str = today_key()
    used = daily_calories.get(date_str, {}).get(user_id, 0)
    limit = get_user_limit(user_id)
    remaining = limit - used

    await message.answer(
        f"Сегодня ты уже набрал {used} ккал.\n"
        f"Лимит: {limit} ккал.\n"
        f"Осталось: {max(remaining, 0)} ккал."
    )


@dp.message_handler(Command("reset_today"))
async def cmd_reset_today(message: types.Message):
    user_id = message.from_user.id
    reset_today_for_user(user_id)
    save_data()
    await message.answer("Сегодняшний счётчик калорий обнулён.")


@dp.message_handler()
async def handle_calories(message: types.Message):
    user_id = message.from_user.id

    # ищем первое число в сообщении
    text = message.text.replace(",", ".")
    parts = text.split()
    cal = None
    for p in parts:
        try:
            cal = int(float(p))
            break
        except ValueError:
            continue

    if cal is None:
        await message.answer("Не понял, сколько ккал. Напиши просто число, например: 350")
        return

    # не даём увести в ад странными значениями
    if abs(cal) > 5000:
        await message.answer("Слишком странное число калорий, давай что-то реальнее :)")
        return

    used, remaining = add_calories(user_id, cal)
    limit = get_user_limit(user_id)
    save_data()

    reply = build_reply_text(cal, remaining, limit)
    await message.answer(reply)


if __name__ == "__main__":
    load_data()
    executor.start_polling(dp, skip_updates=True)

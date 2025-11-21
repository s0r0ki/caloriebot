import asyncio
import logging
import json
import os
from datetime import datetime, time, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import pytz
import random

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

DATA_FILE = "calories.json"
TZ = pytz.timezone("Europe/Moscow")


def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_today():
    return datetime.now(TZ).strftime("%Y-%m-%d")


# ------------------------------
#     РЕАКЦИИ НА ОБЪЁМ ЕДЫ
# ------------------------------

MEAL_REACTIONS = {
    "tiny": [
        "Это было не еда, а тест-драйв.",
        "Перекус-призрак.",
        "Лимит даже не заметил.",
        "Так ест человек с характером.",
        "Можно считать, что «ничего не было».",
        "Организм такой: «и всё?»",
        "Диета довольно улыбается.",
        "Аккуратненько, красиво.",
        "Лёгкий шаг, а не еда.",
        "Просто размял желудок.",
    ],
    "light": [
        "Лёгкий заход, лимит не в стрессе.",
        "Нормальный скромный приём.",
        "Поел — но без последствий.",
        "Чистый, спокойный ход.",
        "Пока всё под контролем.",
        "Диета не напрягается.",
        "Умерено, приятно, не страшно.",
        "Типичный «не стыдно» перекус.",
        "Ещё далеко до проблем.",
        "Симпатичный порционочный формат.",
    ],
    "normal": [
        "Вот это уже еда.",
        "Плотно, но без паники.",
        "Лимит почувствовал, но терпит.",
        "Вкусно и заметно.",
        "Хороший полноценный приём.",
        "Силы есть, свободы меньше.",
        "Норм в пределах дня.",
        "Так можно питаться каждый день.",
        "Плотненько, но разумно.",
        "По-классике — еда как еда.",
    ],
    "heavy": [
        "Мощный заход.",
        "Лимит присел от неожиданности.",
        "Это уже серьёзно.",
        "Так ест человек, который проголодался.",
        "Сыто, громко, внушительно.",
        "Желудок доволен, лимит в напряге.",
        "Ещё немного — и будет много.",
        "Серьёзный приём.",
        "Аппетит явно победил.",
        "Такое лучше не повторять часто.",
    ],
    "huge": [
        "Это был налёт на холодильник.",
        "Лимит сейчас поперхнулся.",
        "Очень мощный приём.",
        "Праздничный объём еды.",
        "Это был монстр-приём.",
        "Диета уже пишет заявление.",
        "Банкет, не иначе.",
        "Сейчас было слишком много.",
        "Очень тяжёлый заход.",
        "Калории кричат от избытка.",
    ],
}

# ------------------------------
#   РЕАКЦИИ ПО ОСТАТКУ ЛИМИТА
# ------------------------------

REMAIN_REACTIONS = {
    "very_safe": [
        "Ты ещё очень далеко от края.",
        "Лимит чистенький, как новый.",
        "Можно есть спокойно.",
        "Запас огромный, кайф.",
        "Играешь на лёгком уровне.",
        "Диета тобой довольна.",
        "Контроль идеальный.",
        "Плывёшь уверенно.",
        "Запас как у танка.",
        "Пока вообще не страшно.",
    ],
    "safe": [
        "Пока всё норм, но уже с умом.",
        "Свобода есть, но не бесконечная.",
        "Спокойная зона.",
        "Можно продолжать, но аккуратнее.",
        "Пока по плану.",
        "Немного подъел, но жить можно.",
        "Ещё не тревожно.",
        "Зона комфорта сохраняется.",
        "Пока зелёный коридор.",
        "Осторожно, но можно.",
    ],
    "tight": [
        "Место заканчивается.",
        "Это уже жёлтая зона.",
        "Каждый кусок теперь — решение.",
        "Лучше подумать, прежде чем есть.",
        "Запас смешной.",
        "Коридор очень узкий.",
        "Лимит почти на пределе.",
        "Ещё чуть-чуть — и всё.",
        "Надо включать голову.",
        "Сейчас легко перебрать.",
    ],
    "danger": [
        "Лимит уже задыхается.",
        "Ты в красной зоне.",
        "Ещё немного — и перелёт.",
        "Лучше остановиться.",
        "Дальше нельзя, если хочешь минус.",
        "Предельно опасный момент.",
        "Ситуация критическая.",
        "Сегодня уже тяжело.",
        "Лимит на последнем издыхании.",
        "Дальше вредно для прогресса.",
    ],
    "doom": [
        "Лимит кончился, день улетел.",
        "Чистый перелёт.",
        "Сегодня плюс по калориям.",
        "Срыв по лимиту уверенный.",
        "Диета сегодня проиграла.",
        "Весы уже плачут.",
        "Полетели за грань.",
        "Этот день точно не про дефицит.",
        "Перебор очевиден.",
        "Выход в космос по калориям.",
    ],
}


def choose_meal_grade(cal):
    if cal < 80:
        return "tiny"
    elif cal < 200:
        return "light"
    elif cal < 450:
        return "normal"
    elif cal < 800:
        return "heavy"
    return "huge"


def choose_remain_grade(remain, limit):
    used = limit - remain

    ratio = used / limit if limit > 0 else 1

    if ratio < 0.25:
        return "very_safe"
    elif ratio < 0.55:
        return "safe"
    elif ratio < 0.8:
        return "tight"
    elif ratio < 1:
        return "danger"
    return "doom"


# ------------------------------
#        КОМАНДЫ БОТА
# ------------------------------

@dp.message(Command("set"))
async def set_limit(message: types.Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Формат: /set 2000 или /set 2000 @username")
        return

    try:
        limit = int(parts[1])
    except:
        await message.answer("Пожалуйста, укажи число.")
        return

    data = load_data()
    today = get_today()

    if today not in data:
        data[today] = {}

    # если указан другой пользователь
    if len(parts) == 3:
        target = parts[2]
    else:
        target = message.from_user.username or str(message.from_user.id)

    if target not in data[today]:
        data[today][target] = {"limit": limit, "used": 0}
    else:
        data[today][target]["limit"] = limit

    save_data(data)
    await message.answer(f"Лимит для {target} установлен: {limit} ккал.")


@dp.message()
async def log_calories(message: types.Message):
    text = message.text.lower().replace(" ", "")
    if not text.endswith("ккал"):
        return

    try:
        calories = int(text.replace("ккал", ""))
    except:
        return

    user_key = message.from_user.username or str(message.from_user.id)

    data = load_data()
    today = get_today()

    if today not in data:
        data[today] = {}

    if user_key not in data[today]:
        data[today][user_key] = {"limit": 2000, "used": 0}

    data[today][user_key]["used"] += calories
    limit = data[today][user_key]["limit"]
    used = data[today][user_key]["used"]
    remain = limit - used

    # выбираем тип реакции
    pick = random.choice(["meal", "remain"])

    if pick == "meal":
        grade = choose_meal_grade(calories)
        reaction = random.choice(MEAL_REACTIONS[grade])
    else:
        grade = choose_remain_grade(remain, limit)
        reaction = random.choice(REMAIN_REACTIONS[grade])

    save_data(data)

    if remain >= 0:
        await message.answer(f"-{calories} ккал. Осталось {remain}. {reaction}")
    else:
        await message.answer(f"-{calories} ккал. Перебор на {abs(remain)}. {reaction}")


# ------------------------------
#   ЕЖЕДНЕВНЫЙ СБРОС В 06:00
# ------------------------------

async def reset_daily():
    while True:
        now = datetime.now(TZ)
        target = now.replace(hour=6, minute=0, second=0, microsecond=0)

        if now >= target:
            target += timedelta(days=1)

        wait_seconds = (target - now).total_seconds()
        await asyncio.sleep(wait_seconds)

        today = get_today()
        save_data({today: {}})


async def main():
    asyncio.create_task(reset_daily())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

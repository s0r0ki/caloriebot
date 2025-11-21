import re
import json
import os
from datetime import datetime, time, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command
import asyncio
import pytz

TOKEN = os.getenv("TELEGRAM_TOKEN")


DATA_FILE = "calories.json"
TZ = pytz.timezone("Asia/Yerevan")


def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


async def reset_daily():
    while True:
        now = datetime.now(TZ)
        target = TZ.localize(datetime.combine(now.date(), time(6, 0)))

        if now > target:
            target += timedelta(days=1)

        wait_time = (target - now).total_seconds()
        await asyncio.sleep(wait_time)

        data = load_data()
        for user_id in data:
            data[user_id]["remaining"] = data[user_id]["limit"]
        save_data(data)


bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(Command("setlimit"))
async def set_limit(message: Message):
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.reply("Используй так: /setlimit 2000")
        return

    limit = int(parts[1])
    user_id = str(message.from_user.id)

    data = load_data()
    data.setdefault(user_id, {"limit": limit, "remaining": limit})
    data[user_id]["limit"] = limit
    data[user_id]["remaining"] = limit
    save_data(data)

    await message.reply(f"Лимит установлен: {limit} ккал")


@dp.message(F.text)
async def process_calories(message: Message):
    text = message.text.lower()
    match = re.search(r"(\d+)\s*(ккал|kcal|кcal|кк|к)", text)

    if not match:
        return

    calories = int(match.group(1))
    user_id = str(message.from_user.id)

    data = load_data()

    if user_id not in data:
        await message.reply("Сначала установи лимит командой: /setlimit 2000")
        return

    data[user_id]["remaining"] -= calories
    remaining = data[user_id]["remaining"]
    save_data(data)

    if remaining >= 0:
        await message.reply(
            f"{message.from_user.first_name}, осталось: {remaining} ккал"
        )
    else:
        await message.reply(
            f"{message.from_user.first_name}, лимит превышён на {-remaining} ккал!"
        )


async def main():
    asyncio.create_task(reset_daily())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

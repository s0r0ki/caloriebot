import os
import json
import pytz
from datetime import datetime, time
from aiogram import Bot, Dispatcher, executor, types

TOKEN = os.getenv("TELEGRAM_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

DATA_FILE = "users.json"
TZ = pytz.timezone("Europe/Moscow")  # можешь поменять на свой

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

def reset_if_needed(user):
    now = datetime.now(TZ)
    if now.hour == 6 and user.get("last_reset") != now.strftime("%Y-%m-%d"):
        user["remaining"] = user["daily"]
        user["last_reset"] = now.strftime("%Y-%m-%d")

@dp.message_handler(commands=["set"])
async def set_limit(message: types.Message):
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        return await message.reply("Использование: /set 2000")

    limit = int(parts[1])
    data = load_data()
    uid = str(message.from_user.id)

    data[uid] = {
        "daily": limit,
        "remaining": limit,
        "last_reset": datetime.now(TZ).strftime("%Y-%m-%d")
    }

    save_data(data)
    await message.reply(f"Твой дневной лимит установлен: {limit} ккал")

@dp.message_handler()
async def count_calories(message: types.Message):
    text = message.text.lower().replace(" ", "")
    if not text.endswith("ккал"):
        return

    num = text[:-4]
    if not num.isdigit():
        return

    amount = int(num)
    data = load_data()
    uid = str(message.from_user.id)

    if uid not in data:
        return await message.reply("Сначала задай лимит: /set 2000")

    user = data[uid]
    reset_if_needed(user)

    user["remaining"] -= amount
    save_data(data)

    if user["remaining"] >= 0:
        await message.reply(f"Осталось: {user['remaining']} ккал")
    else:
        await message.reply(f"Ты превысил лимит на {-user['remaining']} ккал!")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)

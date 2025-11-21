import os
import json
from datetime import datetime
import pytz

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("TELEGRAM_TOKEN")

DATA_FILE = "users.json"
TZ = pytz.timezone("Europe/Moscow")  # можешь поменять на свой часовой пояс


def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def reset_if_needed(user: dict):
    now = datetime.now(TZ)
    today = now.strftime("%Y-%m-%d")

    # Сбрасываем после 6 утра, если дата изменилась
    if user.get("last_reset") != today and now.hour >= 6:
        user["remaining"] = user.get("daily", user.get("remaining", 0))
        user["last_reset"] = today


def get_key(update: Update) -> str:
    # ключ — пара чат+юзер, чтобы вы с девушкой были независимы
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    return f"{chat_id}:{user_id}"


async def set_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 1 or not args[0].isdigit():
        await update.message.reply_text("Использование: /set 2000")
        return

    limit = int(args[0])
    data = load_data()
    key = get_key(update)
    now = datetime.now(TZ).strftime("%Y-%m-%d")

    data[key] = {
        "daily": limit,
        "remaining": limit,
        "last_reset": now,
    }

    save_data(data)
    await update.message.reply_text(f"Твой дневной лимит установлен: {limit} ккал")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    key = get_key(update)

    if key not in data:
        await update.message.reply_text("Сначала задай лимит: /set 2000")
        return

    user = data[key]
    reset_if_needed(user)
    save_data(data)

    await update.message.reply_text(
        f"Твой дневной лимит: {user['daily']} ккал\n"
        f"Осталось на сегодня: {user['remaining']} ккал"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.lower().replace(" ", "")

    # ждём формат типа "300ккал"
    if not text.endswith("ккал"):
        return

    num = text[:-4]
    if not num.isdigit():
        return

    amount = int(num)

    data = load_data()
    key = get_key(update)

    if key not in data:
        await update.message.reply_text("Сначала задай лимит: /set 2000")
        return

    user = data[key]
    reset_if_needed(user)

    user["remaining"] -= amount
    save_data(data)

    if user["remaining"] >= 0:
        await update.message.reply_text(f"Осталось: {user['remaining']} ккал")
    else:
        await update.message.reply_text(
            f"Ты превысил лимит на {-user['remaining']} ккал!"
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я считаю калории.\n"
        "1) Задай лимит: /set 2000\n"
        "2) Пиши в чат сообщения вида: 300ккал\n"
        "3) Я буду вычитать и показывать остаток.\n"
        "Команда /status — показать текущий остаток."
    )


def main():
    if not TOKEN:
        raise RuntimeError("Переменная окружения TELEGRAM_TOKEN не задана")

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("set", set_limit))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    application.run_polling()


if __name__ == "__main__":
    main()

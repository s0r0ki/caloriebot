import os
import json
import random
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
TZ = pytz.timezone("Europe/Moscow")  # можешь сменить на свой часовой пояс


# ====== Хранение данных ======

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


def make_key(chat_id: int, user_id: int) -> str:
    # ключ — пара чат+юзер
    return f"{chat_id}:{user_id}"


def get_key(update: Update) -> str:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    return make_key(chat_id, user_id)


def reset_if_needed(user: dict):
    """
    Сброс лимита один раз в день после 6 утра по TZ.
    """
    now = datetime.now(TZ)
    today = now.strftime("%Y-%m-%d")

    if user.get("last_reset") != today and now.hour >= 6:
        user["remaining"] = user.get("daily", user.get("remaining", 0))
        user["last_reset"] = today


# ====== Реакции ======

REACTIONS_OK = [
    "Живём! 💪",
    "Можно ещё чуть-чуть 😏",
    "Нормально идёшь 🐢",
    "Пока без паники 🔥",
    "Диетолог тобой бы гордился(а) 🩺",
    "Ещё не конец света 🌍",
    "Калории дрожат от страха, но ты молодец 😎",
]

REACTIONS_OVER = [
    "Ну всё, пошли в зал… когда-нибудь 🏋️‍♂️",
    "Мы это… делали вид, что не видели 😶",
    "Лимит: *я устал, я ухожу* 🚪",
    "Организм: *алё, ты серьёзно?* 📞",
    "Калории такие: «он(а) не остановится…» 😱",
    "Это был вкусный бунт против системы 🤷‍♂️",
]


def add_reaction(base_text: str, over: bool = False) -> str:
    if over:
        r = random.choice(REACTIONS_OVER)
    else:
        r = random.choice(REACTIONS_OK)
    return f"{base_text}\n\n{r}"


# ====== Команды ======

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Привет! Я считаю калории в этом чате 🍽\n\n"
        "Как пользоваться:\n"
        "1️⃣ Задай свой лимит: /set 2000\n"
        "2️⃣ Пиши сообщения вида: 300ккал\n"
        "   (без пробелов, можно в любом месте чата)\n"
        "3️⃣ Я буду вычитать и писать, сколько осталось.\n\n"
        "Для другого человека:\n"
        "— ответь на его сообщение и напиши: /setfor 1800\n\n"
        "Посмотреть остаток: /status"
    )
    await update.message.reply_text(text)


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
    msg = f"Твой дневной лимит установлен: {limit} ккал"
    await update.message.reply_text(add_reaction(msg, over=False))


async def set_for_other(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /setfor 1800 в ответ на сообщение другого человека.
    """
    if not update.message:
        return

    if not update.message.reply_to_message:
        await update.message.reply_text(
            "Сделай реплай на сообщение человека и напиши: /setfor 1800"
        )
        return

    args = context.args
    if len(args) != 1 or not args[0].isdigit():
        await update.message.reply_text("Использование: /setfor 1800 (в ответ на сообщение)")
        return

    limit = int(args[0])

    target_user = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id
    key = make_key(chat_id, target_user.id)

    data = load_data()
    now = datetime.now(TZ).strftime("%Y-%m-%d")

    data[key] = {
        "daily": limit,
        "remaining": limit,
        "last_reset": now,
    }

    save_data(data)

    name = target_user.first_name or "пользователь"
    msg = f"Лимит для {name} установлен: {limit} ккал"
    await update.message.reply_text(add_reaction(msg, over=False))


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    key = get_key(update)

    if key not in data:
        await update.message.reply_text("Сначала задай лимит: /set 2000")
        return

    user = data[key]
    reset_if_needed(user)
    save_data(data)

    msg = (
        f"Твой дневной лимит: {user['daily']} ккал\n"
        f"Осталось на сегодня: {user['remaining']} ккал"
    )
    over = user["remaining"] < 0
    await update.message.reply_text(add_reaction(msg, over=over))


# ====== Обработка сообщений с '...ккал' ======

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
        msg = f"Осталось: {user['remaining']} ккал"
        await update.message.reply_text(add_reaction(msg, over=False))
    else:
        msg = f"Ты превысил лимит на {-user['remaining']} ккал!"
        await update.message.reply_text(add_reaction(msg, over=True))


# ====== Запуск приложения ======

def main():
    if not TOKEN:
        raise RuntimeError("Переменная окружения TELEGRAM_TOKEN не задана")

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("set", set_limit))
    application.add_handler(CommandHandler("setfor", set_for_other))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    application.run_polling()


if __name__ == "__main__":
    main()

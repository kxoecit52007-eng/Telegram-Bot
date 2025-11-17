import os
import time
import telebot
from telebot.types import Message
from flask import Flask, request

# ====== CONFIG ======
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

OWNER_ID = 8253247804
ACCESS_PASSWORD = "MetaSnos"     # постоянный ключ доступа
MAX_ATTEMPTS = 5                 # попытки для ввода ключа/пароля
BLOCK_TIME = 60 * 15             # блокировка 15 минут

bot = telebot.TeleBot(BOT_TOKEN)
server = Flask(__name__)

# ====== STORAGE ======
allowed_users = set([OWNER_ID])
temp_keys = {}          # {ключ: expire_time}
used_keys = set()       # уже использованные ключи
failed_attempts = {}    # {user_id: [attempt_count, block_until_time]}


# ====== UTILS ======

def generate_key(length=12):
    import random, string
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def cleanup_temp_keys():
    now = time.time()
    expired = [k for k, exp in temp_keys.items() if exp < now]
    for k in expired:
        del temp_keys[k]


def is_blocked(user_id):
    """Проверка, заблокирован ли пользователь за перебор ключей"""
    if user_id not in failed_attempts:
        return False

    attempts, block_until = failed_attempts[user_id]
    if block_until and block_until > time.time():
        return True

    return False


def register_fail(user_id):
    """Регистрирует ошибку ввода ключа/пароля"""
    now = time.time()
    if user_id not in failed_attempts:
        failed_attempts[user_id] = [1, None]
        return MAX_ATTEMPTS - 1

    attempts, block_until = failed_attempts[user_id]

    if block_until and block_until > now:
        return 0  # уже заблокирован

    attempts += 1
    if attempts >= MAX_ATTEMPTS:
        failed_attempts[user_id] = [attempts, now + BLOCK_TIME]
        return 0
    else:
        failed_attempts[user_id] = [attempts, None]
        return MAX_ATTEMPTS - attempts


def clear_fail(user_id):
    if user_id in failed_attempts:
        del failed_attempts[user_id]


# ====== COMMANDS ======

@bot.message_handler(commands=['start'])
def start(message: Message):
    cleanup_temp_keys()
    user_id = message.from_user.id

    if user_id not in allowed_users:
        bot.reply_to(message, "🚫 У вас нет доступа.\nВведите пароль или ключ:")
        return

    bot.reply_to(message, "👋 Добро пожаловать! Меню: /menu")


@bot.message_handler(commands=['menu'])
def menu(message: Message):
    if message.from_user.id not in allowed_users:
        return
    bot.reply_to(message,
        "📌 Команды:\n"
        "/admin — админ панель\n"
        "/key — постоянный доступ\n"
        "/tempkey <минут> — временный ключ\n"
    )


@bot.message_handler(commands=['admin'])
def admin(message: Message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "⛔ Нет прав.")
        return

    bot.reply_to(message,
        "🔐 *Админ-панель:*\n"
        "/access <id> — выдать доступ\n"
        "/revoke <id> — удалить доступ\n"
        "/users — показать пользователей\n"
        "/tempkey <минут> — временный ключ\n",
        parse_mode="Markdown"
    )


@bot.message_handler(commands=['users'])
def users(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    text = "\n".join(str(uid) for uid in allowed_users)
    bot.reply_to(message, f"📍 Пользователи:\n{text}")


@bot.message_handler(commands=['access'])
def access(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    try:
        uid = int(message.text.split()[1])
        allowed_users.add(uid)
        bot.reply_to(message, f"✅ Доступ выдан {uid}")
    except:
        bot.reply_to(message, "Использование: /access <id>")


@bot.message_handler(commands=['revoke'])
def revoke(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    try:
        uid = int(message.text.split()[1])
        if uid in allowed_users:
            allowed_users.remove(uid)
            bot.reply_to(message, f"🚫 Доступ отозван у {uid}")
        else:
            bot.reply_to(message, "Пользователь не найден.")
    except:
        bot.reply_to(message, "Использование: /revoke <id>")


@bot.message_handler(commands=['key'])
def key(message: Message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "⛔ Нет прав.")
        return
    bot.reply_to(message, f"🔑 Постоянный ключ:\n`{ACCESS_PASSWORD}`", parse_mode="Markdown")


@bot.message_handler(commands=['tempkey'])
def tempkey(message: Message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "⛔ Нет прав.")
        return
    try:
        minutes = int(message.text.split()[1])
        expire = time.time() + minutes * 60
        key = generate_key()
        temp_keys[key] = expire
        bot.reply_to(message, f"⏳ Временный ключ на {minutes} мин:\n`{key}`", parse_mode="Markdown")
    except:
        bot.reply_to(message, "Использование: /tempkey <минут>")


# ====== PASSWORD / KEY LOGIN ======

@bot.message_handler(func=lambda m: True)
def login(message: Message):
    cleanup_temp_keys()
    user_id = message.from_user.id
    text = message.text.strip()

    if user_id in allowed_users:
        clear_fail(user_id)
        return

    if is_blocked(user_id):
        bot.reply_to(message, "⛔ Слишком много неверных попыток. Попробуйте позже.")
        return

    # постоянный
    if text == ACCESS_PASSWORD and text not in used_keys:
        allowed_users.add(user_id)
        used_keys.add(text)
        clear_fail(user_id)
        bot.reply_to(message, "🎉 Доступ получен! /start")
        return

    # временный
    if text in temp_keys and text not in used_keys:
        del temp_keys[text]
        allowed_users.add(user_id)
        used_keys.add(text)
        clear_fail(user_id)
        bot.reply_to(message, "🔓 Временный доступ активирован! /start")
        return

    # неверный ввод
    remaining = register_fail(user_id)
    if remaining == 0:
        bot.reply_to(message, "⛔ Вы заблокированы на 15 минут.")
    else:
        bot.reply_to(message, f"❌ Неверный ключ. Осталось попыток: {remaining}")


# ====== WEBHOOK ======

@server.route("/", methods=["POST"])
def webhook():
    bot.process_new_updates(
        [telebot.types.Update.de_json(request.data.decode("utf-8"))]
    )
    return "OK", 200


if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    server.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

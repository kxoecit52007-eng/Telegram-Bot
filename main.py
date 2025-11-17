import os
import telebot
from flask import Flask, request
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= ENVIRONMENT VARS =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
RENDER_URL = os.getenv("RENDER_URL")  # https://yourname.onrender.com

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)

# ================= USER ACCESS STORAGE =================
users = set()
allowed_users = set([OWNER_ID])  # изначальный доступ только у владельца


def is_allowed(uid):
    return uid in allowed_users or uid == OWNER_ID


# ================= HANDLERS =================

@bot.message_handler(commands=["start"])
def start(message):
    user_id = message.from_user.id
    users.add(user_id)

    if not is_allowed(user_id):
        return bot.send_message(
            user_id, "⛔ У вас нет доступа к боту.\nЗапросите доступ у администратора."
        )
    bot.send_message(user_id, "Добро пожаловать! Доступ подтверждён 🔓")


@bot.message_handler(commands=["admin"])
def admin_panel(message):
    if message.from_user.id != OWNER_ID:
        return bot.send_message(message.chat.id, "⛔ Вы не администратор.")

    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("📊 Статистика", callback_data="stats"),
        InlineKeyboardButton("📢 Рассылка", callback_data="broadcast")
    )
    markup.row(
        InlineKeyboardButton("➕ Выдать доступ", callback_data="grant_access"),
        InlineKeyboardButton("❌ Забрать доступ", callback_data="remove_access")
    )
    markup.row(InlineKeyboardButton("👥 Список пользователей", callback_data="list_users"))
    bot.send_message(message.chat.id, "Админ-панель ⚙️", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    uid = call.from_user.id
    if uid != OWNER_ID:
        return bot.answer_callback_query(call.id, "⛔ Нет доступа")

    if call.data == "stats":
        bot.send_message(uid, f"📊 Всего пользователей: {len(users)}\n🔑 Имеют доступ: {len(allowed_users)}")

    elif call.data == "list_users":
        if users:
            bot.send_message(uid, "👥 Пользователи:\n" + "\n".join(str(u) for u in users))
        else:
            bot.send_message(uid, "Нет зарегистрированных пользователей.")

    elif call.data == "broadcast":
        msg = bot.send_message(uid, "Введите текст рассылки:")
        bot.register_next_step_handler(msg, do_broadcast)

    elif call.data == "grant_access":
        msg = bot.send_message(uid, "Введите ID пользователя, которому дать доступ:")
        bot.register_next_step_handler(msg, grant_access)

    elif call.data == "remove_access":
        msg = bot.send_message(uid, "Введите ID пользователя, у которого забрать доступ:")
        bot.register_next_step_handler(msg, remove_access)


def do_broadcast(message):
    text = message.text
    for uid in users:
        try:
            bot.send_message(uid, text)
        except:
            pass
    bot.send_message(message.from_user.id, "📢 Рассылка отправлена!")


def grant_access(message):
    try:
        uid = int(message.text)
        allowed_users.add(uid)
        bot.send_message(message.chat.id, f"Пользователь {uid} теперь имеет доступ 🔓")
    except:
        bot.send_message(message.chat.id, "❗ Ошибка: неверный ID")


def remove_access(message):
    try:
        uid = int(message.text)
        if uid == OWNER_ID:
            return bot.send_message(message.chat.id, "❗ Нельзя удалить владельца")
        allowed_users.discard(uid)
        bot.send_message(message.chat.id, f"Доступ пользователя {uid} удалён ⛔")
    except:
        bot.send_message(message.chat.id, "❗ Ошибка: неверный ID")


# ================= WEBHOOK =================

@app.route("/" + BOT_TOKEN, methods=["POST"])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.data.decode("utf-8"))])
    return "OK", 200


@app.route("/")
def index():
    return "Telegram bot is running!", 200


if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"{RENDER_URL}/{BOT_TOKEN}")
    app.run(host="0.0.0.0", port=10000)

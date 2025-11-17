import os
import telebot
from flask import Flask, request

TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))  # твой Telegram ID
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://имя.onrender.com/webhook

bot = telebot.TeleBot(TOKEN)
allowed_users = {OWNER_ID}  # изначально доступ есть только у владельца

# === Команда старт ===
@bot.message_handler(commands=['start'])
def start(message):
    if message.from_user.id not in allowed_users:
        return bot.reply_to(message,
            "⚠ У вас нет доступа к этому боту.\n"
            "Свяжитесь с владельцем чтобы получить доступ."
        )

    bot.reply_to(message, "👋 Добро пожаловать! Вы авторизованы.\n/menu — открыть меню.")

# === Меню ===
@bot.message_handler(commands=['menu'])
def menu(message):
    if message.from_user.id != OWNER_ID:
        return bot.reply_to(message, "❌ Доступ запрещён.")

    text = (
        "🔐 *Админ-панель*\n\n"
        "Команды:\n"
        "`/add ID` — выдать доступ\n"
        "`/remove ID` — убрать доступ\n"
        "`/users` — список пользователей\n"
        "`/broadcast текст` — рассылка\n"
    )
    bot.reply_to(message, text, parse_mode="Markdown")

# === Добавить пользователя ===
@bot.message_handler(commands=['add'])
def add_user(message):
    if message.from_user.id != OWNER_ID:
        return

    try:
        user_id = int(message.text.split()[1])
        allowed_users.add(user_id)
        bot.reply_to(message, f"✅ Пользователь {user_id} получил доступ.")
    except:
        bot.reply_to(message, "Использование: /add USER_ID")

# === Удалить пользователя ===
@bot.message_handler(commands=['remove'])
def remove_user(message):
    if message.from_user.id != OWNER_ID:
        return

    try:
        user_id = int(message.text.split()[1])
        allowed_users.discard(user_id)
        bot.reply_to(message, f"❌ Пользователь {user_id} удалён из доступа.")
    except:
        bot.reply_to(message, "Использование: /remove USER_ID")

# === Список пользователей ===
@bot.message_handler(commands=['users'])
def show_users(message):
    if message.from_user.id != OWNER_ID:
        return

    if not allowed_users:
        return bot.reply_to(message, "Список пуст.")

    text = "👥 Пользователи с доступом:\n" + "\n".join(str(u) for u in allowed_users)
    bot.reply_to(message, text)

# === Рассылка ===
@bot.message_handler(commands=['broadcast'])
def broadcast(message):
    if message.from_user.id != OWNER_ID:
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return bot.reply_to(message, "Использование: /broadcast текст")

    text = parts[1]
    for user in allowed_users:
        try:
            bot.send_message(user, text)
        except:
            pass

    bot.reply_to(message, "📨 Рассылка завершена.")

# === Flask сервер ===
app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
    bot.process_new_updates([update])
    return "ok", 200

# === Запуск ===
if __name__ == "__main__":
    print("Starting bot with webhook...")
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

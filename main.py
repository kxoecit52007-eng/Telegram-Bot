import os
from flask import Flask, request
from telegram import Update, Bot, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackContext

# =============================
# 🔧 ENV CONFIG
# =============================
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://your-app.onrender.com/webhook
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not TOKEN:
    raise Exception("❌ BOT_TOKEN отсутствует в переменных окружения!")

bot = Bot(token=TOKEN)

# =============================
# 📦 Хранилище данных
# =============================
users = set()          # ID пользователей с доступом
keys = {}              # ключи: key -> attempts_left
MAX_ATTEMPTS = 3       # попыток на ключ

# =============================
# 🎛 Кнопочные меню
# =============================
def user_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🔑 Ввести ключ")],
        [KeyboardButton("ℹ О боте")],
    ], resize_keyboard=True)

def admin_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🔑 Ввести ключ")],
        [KeyboardButton("📢 Рассылка"), KeyboardButton("👥 Пользователи")],
        [KeyboardButton("➕ Добавить ключ"), KeyboardButton("🗑 Удалить ключ")],
        [KeyboardButton("ℹ О боте")],
    ], resize_keyboard=True)

# =============================
# 🛠 Flask APP
# =============================
app = Flask(__name__)
dispatcher = Dispatcher(bot, None, workers=0)

# =============================
# 👋 Приветствие
# =============================
def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    if user_id in users:
        menu = admin_menu() if user_id == ADMIN_ID else user_menu()
        update.message.reply_text(
            "🔓 Добро пожаловать! Доступ активен.\nВыберите действие:",
            reply_markup=menu
        )
    else:
        update.message.reply_text(
            "👋 Добро пожаловать!\n\n"
            "🔐 Чтобы получить доступ, нажмите кнопку ниже и введите ключ:",
            reply_markup=user_menu()
        )

# =============================
# ℹ О боте
# =============================
def about(update: Update, context: CallbackContext):
    update.message.reply_text(
        "🤖 MetaSnos Bot\n\n"
        "Бот с приватным доступом по ключам.\n"
        "Функционал доступен только одобренным пользователям. 🔐"
    )

# =============================
# 🔑 Обработка ключей
# =============================
def process_key(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_id in users:
        return update.message.reply_text("🎉 У вас уже есть доступ!")

    if text not in keys:
        return update.message.reply_text("❌ Неверный ключ, попробуйте снова.")

    if keys[text] <= 0:
        return update.message.reply_text("🚫 У этого ключа больше нет попыток.")

    keys[text] -= 1
    users.add(user_id)
    update.message.reply_text("🔓 Доступ успешно выдан! Поздравляю 🎉", reply_markup=user_menu())

# =============================
# 🧰 ADMIN Ограничение
# =============================
def admin_only(func):
    def wrapper(update: Update, context: CallbackContext):
        if update.effective_user.id != ADMIN_ID:
            return update.message.reply_text("⛔ У вас нет прав администратора.")
        return func(update, context)
    return wrapper

# =============================
# 👥 ADMIN: список пользователей
# =============================
@admin_only
def list_users(update: Update, context: CallbackContext):
    if not users:
        return update.message.reply_text("👤 Пока нет пользователей.")
    update.message.reply_text("👥 Пользователи:\n" + "\n".join(map(str, users)))

# =============================
# ➕ ADMIN: добавить ключ
# =============================
@admin_only
def add_key(update: Update, context: CallbackContext):
    try:
        key = context.args[0]
        keys[key] = MAX_ATTEMPTS
        update.message.reply_text(f"🔑 Ключ '{key}' добавлен.")
    except:
        update.message.reply_text("⚠ Использование: /add_key ключ")

# =============================
# 🗑 ADMIN: удалить ключ
# =============================
@admin_only
def del_key(update: Update, context: CallbackContext):
    try:
        key = context.args[0]
        if key in keys:
            del keys[key]
            update.message.reply_text(f"🗑 Ключ '{key}' удалён.")
        else:
            update.message.reply_text("❌ Нет такого ключа.")
    except:
        update.message.reply_text("⚠ Использование: /del_key ключ")

# =============================
# 📢 ADMIN: рассылка
# =============================
@admin_only
def broadcast(update: Update, context: CallbackContext):
    text = " ".join(context.args)
    if not text:
        return update.message.reply_text("⚠ Использование: /broadcast текст")

    sent = 0
    for uid in users:
        try:
            bot.send_message(uid, f"📢 Объявление администратора:\n\n{text}")
            sent += 1
        except:
            pass
    update.message.reply_text(f"📨 Рассылка завершена. Отправлено: {sent}")

# =============================
# 🧠 Обработка текстовых кнопок
# =============================
def text_router(update: Update, context: CallbackContext):
    text = update.message.text

    if text == "ℹ О боте":
        return about(update, context)

    if text == "🔑 Ввести ключ":
        return update.message.reply_text("Введите ключ:")

    if text == "📢 Рассылка" and update.effective_user.id == ADMIN_ID:
        return update.message.reply_text("Введите сообщение:\n\n/broadcast текст")

    if text == "👥 Пользователи" and update.effective_user.id == ADMIN_ID:
        return list_users(update, context)

    if text == "➕ Добавить ключ" and update.effective_user.id == ADMIN_ID:
        return update.message.reply_text("Использование:\n/add_key ключ")

    if text == "🗑 Удалить ключ" and update.effective_user.id == ADMIN_ID:
        return update.message.reply_text("Использование:\n/del_key ключ")

    return process_key(update, context)

# =============================
# Handlers
# =============================
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("add_key", add_key))
dispatcher.add_handler(CommandHandler("del_key", del_key))
dispatcher.add_handler(CommandHandler("users", list_users))
dispatcher.add_handler(CommandHandler("broadcast", broadcast))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, text_router))

# =============================
# 🌐 Webhook endpoint
# =============================
@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(), bot)
    dispatcher.process_update(update)
    return "OK", 200

if WEBHOOK_URL:
    bot.set_webhook(WEBHOOK_URL)
    print("Webhook установлен:", WEBHOOK_URL)

@app.route("/")
def home():
    return "Bot running!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

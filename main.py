import os
import telebot

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = telebot.TeleBot(BOT_TOKEN)

# ID владельца (ты)
OWNER_ID = 8253247804

# Здесь храним разрешённых пользователей
allowed_users = {OWNER_ID}

def is_allowed(user_id):
    return user_id in allowed_users or user_id == OWNER_ID


# Команда /start
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    
    if not is_allowed(user_id):
        bot.reply_to(message, "⛔ У вас нет доступа к этому боту.")
        return
    
    bot.reply_to(message, "🔐 Добро пожаловать! У вас есть доступ к функциям бота.")


# Команда /adduser <id> — только для владельца
@bot.message_handler(commands=['adduser'])
def add_user(message):
    if message.from_user.id != OWNER_ID:
        return bot.reply_to(message, "⛔ Команда доступна только владельцу.")

    try:
        new_id = int(message.text.split()[1])
        allowed_users.add(new_id)
        bot.reply_to(message, f"✔ Пользователь {new_id} добавлен в список доступа.")
    except:
        bot.reply_to(message, "❗ Использование: /adduser <id>")


# Команда /deluser <id> — только для владельца
@bot.message_handler(commands=['deluser'])
def del_user(message):
    if message.from_user.id != OWNER_ID:
        return bot.reply_to(message, "⛔ Команда только для владельца.")
    
    try:
        remove_id = int(message.text.split()[1])
        if remove_id in allowed_users:
            allowed_users.remove(remove_id)
            bot.reply_to(message, f"❌ Пользователь {remove_id} удалён из доступа.")
        else:
            bot.reply_to(message, "Пользователь и так не имел доступа.")
    except:
        bot.reply_to(message, "❗ Использование: /deluser <id>")


# Любой другой текст — только если есть доступ
@bot.message_handler(func=lambda m: True)
def main_logic(message):
    if not is_allowed(message.from_user.id):
        return bot.reply_to(message, "⛔ У вас нет доступа.")
    
    bot.reply_to(message, f"🟢 Вы можете пользоваться ботом.\nВаш текст: {message.text}")


print("Bot started...")
bot.infinity_polling()

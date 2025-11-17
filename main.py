import os
import telebot
from flask import Flask, request

TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))

bot = telebot.TeleBot(TOKEN)
server = Flask(__name__)

@bot.message_handler(commands=['start'])
def start(message):
    if message.from_user.id != OWNER_ID:
        return bot.reply_to(message, "⛔ У вас нет доступа к функциям бота.")
    bot.reply_to(message, "🔥 Привет, владелец! Бот работает 24/7 через webhook!")

@server.route('/' + TOKEN, methods=['POST'])
def getMessage():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "OK", 200

@server.route("/")
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url=f"{os.getenv('RENDER_EXTERNAL_URL')}/{TOKEN}")
    return "Webhook set", 200


if __name__ == "__main__":
    server.run(host="0.0.0.0", port=10000)

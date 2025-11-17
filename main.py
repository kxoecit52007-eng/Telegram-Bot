import os
import telebot
from flask import Flask, request

TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)
server = Flask(__name__)

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Привет! Бот запущен и работает 24/7 🌐")

@server.route("/", methods=["POST"])
def receive_update():
    json_str = request.data.decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

@server.route("/", methods=["GET"])
def set_webhook():
    bot.remove_webhook()
    webhook_url = os.getenv("RENDER_EXTERNAL_URL")
    if webhook_url:
        bot.set_webhook(webhook_url)
        return "Webhook set", 200
    return "No RENDER_EXTERNAL_URL found", 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    server.run(host="0.0.0.0", port=port)

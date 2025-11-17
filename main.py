import os
import requests
from fastapi import FastAPI, Request
from dotenv import load_dotenv
from database import init_db, add_user, activate_key, user_has_access, create_key, get_all_users

load_dotenv()
init_db()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8453302588:AAF3Yq8YeqYNeESsnZNGEmJL9MXGvKVIleo")
OWNER_ID = int(os.getenv("OWNER_ID", "8253247804"))  # твой ID
API = f"https://api.telegram.org/bot8453302588:AAF3Yq8YeqYNeESsnZNGEmJL9MXGvKVIleo/"

app = FastAPI()


def send_message(chat_id, text, keyboard=None):
    data = {"chat_id": chat_id, "text": text}
    if keyboard:
        data["reply_markup"] = keyboard
    requests.post(API + "sendMessage", json=data)


def menu_keyboard():
    return {
        "keyboard": [
            [{"text": "🔑 Активировать ключ"}],
            [{"text": "ℹ Профиль"}]
        ],
        "resize_keyboard": True
    }


def admin_keyboard():
    return {
        "keyboard": [
            [{"text": "➕ Создать ключ"}],
            [{"text": "📢 Рассылка"}]
        ],
        "resize_keyboard": True
    }


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()

    if "message" not in data:
        return {"ok": True}

    msg = data["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")
    user_id = msg["from"]["id"]

    add_user(user_id)

    # Команда старт
    if text == "/start":
        send_message(chat_id,
                     "👋 Привет!\nДобро пожаловать в бота.\n\n"
                     "Чтобы пользоваться функциями — активируй ключ 🔑",
                     menu_keyboard())
        return {"ok": True}

    # Админ панель
    if user_id == OWNER_ID:
        if text == "/admin":
            send_message(chat_id, "👑 Админ панель", admin_keyboard())
            return {"ok": True}

        if text == "➕ Создать ключ":
            new_key = os.urandom(4).hex()
            create_key(new_key)
            send_message(chat_id, f"🔑 Ключ создан:\n`{new_key}`")
            return {"ok": True}

        if text == "📢 Рассылка":
            send_message(chat_id, "Введи текст рассылки:")
            return {"ok": True}

    # Активация ключа
    if text == "🔑 Активировать ключ":
        send_message(chat_id, "Введи ключ:")
        return {"ok": True}

    if len(text) >= 8 and all(c.isalnum() for c in text):
        result = activate_key(user_id, text)
        send_message(chat_id, result, menu_keyboard())
        return {"ok": True}

    # Профиль
    if text == "ℹ Профиль":
        status = "Есть доступ ✅" if user_has_access(user_id) else "Нет доступа ❌"
        send_message(chat_id, f"👤 Профиль:\nID: `{user_id}`\nДоступ: {status}")
        return {"ok": True}

    send_message(chat_id, "Не понял команду 🤔")
    return {"ok": True}


@app.get("/")
async def root():
    return {"status": "bot running"}

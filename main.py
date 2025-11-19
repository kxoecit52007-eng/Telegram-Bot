import requests
import time

TOKEN = "8453302588:AAF3Yq8YeqYNeESsnZNGEmJL9MXGvKVIleo"
API_URL = f"https://api.telegram.org/bot8453302588:AAF3Yq8YeqYNeESsnZNGEmJL9MXGvKVIleo/"

# ---- Функции ----

def send_message(chat_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = reply_markup
    requests.post(API_URL + "sendMessage", json=data)

def get_user_profile(user_id):
    r = requests.get(API_URL + f"getUserProfilePhotos?user_id={user_id}&limit=1").json()
    try:
        file_id = r["result"]["photos"][0][0]["file_id"]
        return file_id
    except:
        return None

def send_photo(chat_id, file_id, caption):
    data = {"chat_id": chat_id, "photo": file_id, "caption": caption}
    requests.post(API_URL + "sendPhoto", json=data)

# ---- Главное меню ----

MAIN_MENU = {
    "keyboard": [
        ["Пожаловаться на аккаунт"],
        ["Профиль"],
        ["Подписка"]
    ],
    "resize_keyboard": True
}

# ---- Основной цикл ----

def main():
    last_update = 0
    print("Бот запущен!")

    while True:
        try:
            updates = requests.get(API_URL + f"getUpdates?offset={last_update + 1}").json()

            for update in updates.get("result", []):
                last_update = update["update_id"]

                if "message" not in update:
                    continue

                msg = update["message"]
                chat_id = msg["chat"]["id"]
                text = msg.get("text", "")

                # Приветствие + меню
                if text == "/start":
                    send_message(
                        chat_id,
                        "👋 Привет! Я бот MetaSnos.\nВыбери действие ниже:",
                        reply_markup={"keyboard": MAIN_MENU["keyboard"], "resize_keyboard": True}
                    )
                    continue

                # --- Кнопки ---
                if text == "Пожаловаться на аккаунт":
                    send_message(chat_id, "⚠ Функция находится в разработке...")
                    continue

                if text == "Подписка":
                    send_message(chat_id, "💎 Раздел подписок скоро будет готов...")
                    continue

                if text == "Профиль":
                    user = msg["from"]
                    uid = user["id"]
                    uname = user.get("username", "нет")
                    fname = user.get("first_name", "нет")
                    lname = user.get("last_name", "нет")

                    # Получаем аватар
                    photo_id = get_user_profile(uid)

                    caption = (
                        "<b>👤 Ваш профиль</b>\n\n"
                        f"🆔 ID: <code>{uid}</code>\n"
                        f"👤 Имя: {fname}\n"
                        f"👥 Фамилия: {lname}\n"
                        f"📛 Username: @{uname}\n"
                        f"📅 Регистрация: неизвестно (Telegram не даёт дату)\n"
                    )

                    if photo_id:
                        send_photo(chat_id, photo_id, caption)
                    else:
                        send_message(chat_id, caption)

                    continue

            time.sleep(1)

        except Exception as e:
            print("Ошибка:", e)
            time.sleep(2)

# ---- Старт ----
if __name__ == "__main__":
    main()

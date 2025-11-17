  # main.py
import os
import json
import time
import secrets
from datetime import datetime, timezone, timedelta
from flask import Flask, request
import telebot

# --- Config from ENV ---
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")  # без завершающего /
OWNER_ID = str(os.getenv("OWNER_ID", "")).strip()

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in environment variables.")
if not WEBHOOK_URL:
    raise RuntimeError("WEBHOOK_URL is not set in environment variables.")
if not OWNER_ID:
    raise RuntimeError("OWNER_ID is not set in environment variables.")

DATA_FILE = "data.json"

# --- Telebot + Flask ---
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# --- Helpers: persistent storage for admins / keys / allowed users ---
def load_data():
    if not os.path.exists(DATA_FILE):
        # initial structure
        data = {
            "admins": [OWNER_ID],       # list of user ids as strings
            "allowed": {},              # user_id -> expiry_ts (int epoch)
            "keys": {}                  # key -> {expires:ts, max_uses:int, uses:int, used_by:[], issued_by:id}
        }
        save_data(data)
        return data
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_admin(user_id):
    data = load_data()
    return str(user_id) in data.get("admins", [])

def is_allowed(user_id):
    data = load_data()
    user_id = str(user_id)
    expiry = data.get("allowed", {}).get(user_id)
    if not expiry:
        return False
    return int(expiry) > int(time.time())

def grant_temporary_access(user_id, minutes):
    data = load_data()
    expiry_ts = int(time.time()) + int(minutes) * 60
    data.setdefault("allowed", {})[str(user_id)] = expiry_ts
    save_data(data)
    return expiry_ts

def revoke_access(user_id):
    data = load_data()
    if str(user_id) in data.get("allowed", {}):
        del data["allowed"][str(user_id)]
        save_data(data)
        return True
    return False

# --- Key generation / usage ---
def create_key(ttl_minutes=60, max_uses=1, issued_by=None):
    data = load_data()
    key = secrets.token_urlsafe(12)
    data.setdefault("keys", {})[key] = {
        "expires": int(time.time()) + int(ttl_minutes) * 60,
        "max_uses": int(max_uses),
        "uses": 0,
        "used_by": [],
        "issued_by": str(issued_by) if issued_by else None
    }
    save_data(data)
    return key

def use_key(key, user_id):
    data = load_data()
    entry = data.get("keys", {}).get(key)
    now = int(time.time())
    if not entry:
        return (False, "Key not found.")
    if entry["expires"] < now:
        return (False, "Key expired.")
    if str(user_id) in entry.get("used_by", []):
        return (False, "You already used this key.")
    if entry["uses"] >= entry["max_uses"]:
        return (False, "Key has no remaining uses.")
    # Accept usage
    entry["uses"] += 1
    entry.setdefault("used_by", []).append(str(user_id))
    save_data(data)
    return (True, "Key accepted.")

# --- Commands handlers ---
@bot.message_handler(commands=['start'])
def cmd_start(message):
    bot.reply_to(message, "Привет! Это бот с системой доступа. Используй /help для списка команд.")

@bot.message_handler(commands=['help'])
def cmd_help(message):
    help_text = (
        "/help - этот текст\n"
        "/status - проверить ваш доступ\n"
        "/usekey <key> - активировать ключ доступа\n"
        "/key - (admins) сгенерировать временный ключ: /key <minutes> <max_uses>\n"
        "/grant <user_id> <minutes> - (admins) выдать доступ пользователю на минуты\n"
        "/revoke <user_id> - (admins) забрать доступ\n"
        "/addadmin <user_id> - (owner only) добавить администратора\n"
        "/removeadmin <user_id> - (owner only) убрать администратора\n"
        "/admin - открыть краткую админ-панель (текстовая)\n"
    )
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['status'])
def cmd_status(message):
    uid = str(message.from_user.id)
    if is_allowed(uid):
        expiry = load_data()["allowed"][uid]
        dt = datetime.fromtimestamp(int(expiry), tz=timezone.utc).astimezone()
        bot.reply_to(message, f"У вас есть доступ до: {dt.isoformat()}")
    else:
        bot.reply_to(message, "У вас сейчас нет доступа. Получите ключ у администратора или используйте /usekey <key>")

@bot.message_handler(commands=['usekey'])
def cmd_usekey(message):
    parts = message.text.strip().split()
    if len(parts) < 2:
        bot.reply_to(message, "Использование: /usekey <key>")
        return
    key = parts[1].strip()
    ok, info = use_key(key, message.from_user.id)
    if not ok:
        bot.reply_to(message, f"Ключ не подошёл: {info}")
        return
    # при успешном использовании даём временный доступ, например 60 минут по умолчанию
    expiry_ts = int(time.time()) + 60*60
    data = load_data()
    data.setdefault("allowed", {})[str(message.from_user.id)] = expiry_ts
    save_data(data)
    dt = datetime.fromtimestamp(expiry_ts, tz=timezone.utc).astimezone()
    bot.reply_to(message, f"Ключ принят. У вас доступ до {dt.isoformat()}")

@bot.message_handler(commands=['admin'])
def cmd_admin(message):
    uid = str(message.from_user.id)
    if not is_admin(uid) and uid != OWNER_ID:
        bot.reply_to(message, "Только администраторы могут использовать эти команды.")
        return
    text = (
        "Админ-панель (текстовая):\n"
        "/key <minutes> <max_uses> - создать ключ\n"
        "/grant <user_id> <minutes> - выдать доступ\n"
        "/revoke <user_id> - отозвать доступ\n"
        "/addadmin <user_id> - добавить администратора (owner only)\n"
        "/removeadmin <user_id> - убрать администратора (owner only)\n"
    )
    bot.reply_to(message, text)

@bot.message_handler(commands=['key'])
def cmd_key(message):
    uid = str(message.from_user.id)
    if not is_admin(uid) and uid != OWNER_ID:
        bot.reply_to(message, "Только администраторы могут выдавать ключи.")
        return
    parts = message.text.strip().split()
    if len(parts) < 2:
        bot.reply_to(message, "Использование: /key <minutes> [max_uses]\nПример: /key 60 1")
        return
    minutes = int(parts[1])
    max_uses = int(parts[2]) if len(parts) >= 3 else 1
    key = create_key(ttl_minutes=minutes, max_uses=max_uses, issued_by=uid)
    bot.reply_to(message, f"Ключ: `{key}`\nДействует {minutes} мин, max uses: {max_uses}", parse_mode='Markdown')

@bot.message_handler(commands=['grant'])
def cmd_grant(message):
    uid = str(message.from_user.id)
    if not is_admin(uid) and uid != OWNER_ID:
        bot.reply_to(message, "Только администраторы могут выдавать доступ.")
        return
    parts = message.text.strip().split()
    if len(parts) < 3:
        bot.reply_to(message, "Использование: /grant <user_id> <minutes>")
        return
    target = parts[1]
    minutes = int(parts[2])
    expiry = grant_temporary_access(target, minutes)
    dt = datetime.fromtimestamp(expiry, tz=timezone.utc).astimezone()
    bot.reply_to(message, f"Выдан доступ пользователю {target} до {dt.isoformat()}")

@bot.message_handler(commands=['revoke'])
def cmd_revoke(message):
    uid = str(message.from_user.id)
    if not is_admin(uid) and uid != OWNER_ID:
        bot.reply_to(message, "Только администраторы могут отзывать доступ.")
        return
    parts = message.text.strip().split()
    if len(parts) < 2:
        bot.reply_to(message, "Использование: /revoke <user_id>")
        return
    target = parts[1]
    ok = revoke_access(target)
    if ok:
        bot.reply_to(message, f"Доступ у {target} отозван.")
    else:
        bot.reply_to(message, f"У {target} не было активного доступа.")

@bot.message_handler(commands=['addadmin'])
def cmd_addadmin(message):
    if str(message.from_user.id) != OWNER_ID:
        bot.reply_to(message, "Только владелец может добавлять админов.")
        return
    parts = message.text.strip().split()
    if len(parts) < 2:
        bot.reply_to(message, "Использование: /addadmin <user_id>")
        return
    target = parts[1]
    data = load_data()
    if target in data.get("admins", []):
        bot.reply_to(message, f"{target} уже является админом.")
        return
    data.setdefault("admins", []).append(str(target))
    save_data(data)
    bot.reply_to(message, f"{target} добавлен в админы.")

@bot.message_handler(commands=['removeadmin'])
def cmd_removeadmin(message):
    if str(message.from_user.id) != OWNER_ID:
        bot.reply_to(message, "Только владелец может удалять админов.")
        return
    parts = message.text.strip().split()
    if len(parts) < 2:
        bot.reply_to(message, "Использование: /removeadmin <user_id>")
        return
    target = parts[1]
    data = load_data()
    if target not in data.get("admins", []):
        bot.reply_to(message, f"{target} не найден в списке админов.")
        return
    data["admins"].remove(target)
    save_data(data)
    bot.reply_to(message, f"{target} исключен из админов.")

# --- Example: protect main functionality ---
# Здесь можно добавить обработчик основного функционала бота, и разрешать только allowed users.
@bot.message_handler(func=lambda m: True)
def fallback(m):
    # любой общий функционал — доступен только тем у кого есть разрешение
    if is_allowed(m.from_user.id) or is_admin(str(m.from_user.id)) or str(m.from_user.id) == OWNER_ID:
        # Тут оставить существующий функционал, например приветствие
        if m.text and m.text.lower().startswith("hello") or m.text and "привет" in m.text.lower():
            bot.reply_to(m, f"Привет, {m.from_user.first_name}! У тебя есть доступ.")
        else:
            bot.reply_to(m, "Команда не распознана. Используйте /help.")
    else:
        bot.reply_to(m, "У вас нет доступа к функциям бота. Получите ключ у администратора или используйте /usekey <key>")

# --- Webhook routes ---
@app.route('/' + TOKEN, methods=['POST'])
def webhook_handler():
    try:
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
    except Exception as e:
        # логируем, но не ломаем
        print("Webhook error:", e)
    return "OK", 200

@app.route('/')
def index():
    return "Bot is running!", 200

# --- Setup webhook on start ---
def setup_webhook():
    try:
        bot.remove_webhook()
    except Exception:
        pass
    # WEBHOOK_URL должен быть без токена, мы добавим токен при регистрации:
    url = WEBHOOK_URL.rstrip("/") + "/" + TOKEN
    res = bot.set_webhook(url=url)
    print("Webhook set result:", res, "to", url)

if __name__ == "__main__":
    # Ensure data file exists
    load_data()
    setup_webhook()
    port = int(os.getenv("PORT", 5000))
    # Run Flask
    app.run(host="0.0.0.0", port=port)

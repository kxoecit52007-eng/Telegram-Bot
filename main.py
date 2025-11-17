# main.py
# Требования: pyTelegramBotAPI (telebot), Flask
# Переменные окружения (на Render):
# BOT_TOKEN - токен телеграм-бота
# OWNER_ID - твой Telegram ID (число). Будет владелец/админ.
# WEBHOOK - полный URL вебхука, куда Telegram будет слать обновления (например: https://your-domain.com/).
#            Если Telegram требует путь с токеном, укажи полный путь. Важно: этот URL должен быть доступен извне.

import os
import time
import threading
import secrets
from flask import Flask, request
import telebot

# --- Настройки ключей ---
KEY_TTL_SECONDS = 6 * 60 * 60   # 6 часов (вариант B)
KEY_MAX_USES = 1                # каждое ключевое использование можно активировать 1 раз
KEY_MAX_ATTEMPTS = 1            # ограничение попыток (если кто-то пытался использовать ключ — он засчитывается)

# --- Инициализация ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = os.getenv("OWNER_ID")  # строка
WEBHOOK_URL = os.getenv("WEBHOOK")  # полный URL, который Telegram будет POST'ить

if not BOT_TOKEN:
    raise RuntimeError("No BOT_TOKEN set in env")
if not OWNER_ID:
    raise RuntimeError("No OWNER_ID set in env")
if not WEBHOOK_URL:
    raise RuntimeError("No WEBHOOK set in env")

try:
    OWNER_ID_INT = int(OWNER_ID)
except:
    raise RuntimeError("OWNER_ID must be an integer string")

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)
server = Flask(__name__)

# --- In-memory storage (D) ---
allowed_users = set([OWNER_ID_INT])  # владельца добавляем сразу
# keys: key_str -> { 'created': ts, 'uses_left': int, 'attempts': int }
keys = {}
# optionally keep a small log of issued keys -> owner/admin can list if needed
issued_keys = {}

storage_lock = threading.Lock()

# --- Helper functions ---
def is_admin(user_id: int) -> bool:
    return user_id == OWNER_ID_INT

def cleanup_expired_keys():
    """Запускается в фоне — удаляет просроченные ключи."""
    while True:
        now = time.time()
        with storage_lock:
            expired = [k for k,v in keys.items() if now - v['created'] > KEY_TTL_SECONDS or v['uses_left'] <= 0]
            for k in expired:
                keys.pop(k, None)
        time.sleep(60)

def generate_key():
    k = secrets.token_urlsafe(8)  # короткий удобный ключ
    with storage_lock:
        keys[k] = {
            'created': time.time(),
            'uses_left': KEY_MAX_USES,
            'attempts': 0
        }
        issued_keys[k] = time.time()
    return k

# --- Commands ---

@bot.message_handler(commands=['start'])
def cmd_start(message):
    user_id = message.from_user.id
    bot.reply_to(message, "Привет! Бот запущен. Используй /menu чтобы увидеть доступные команды.")
    
@bot.message_handler(commands=['menu'])
def cmd_menu(message):
    uid = message.from_user.id
    if is_admin(uid):
        text = ("🔐 Админ-панель\n"
                "Команды:\n"
                "/add <id> — выдать доступ\n"
                "/remove <id> — убрать доступ\n"
                "/users — список пользователей\n"
                "/genkey — сгенерировать временный ключ (6ч, 1 использование)\n"
                "/revoke_key <key> — отозвать ключ\n"
                "/broadcast <текст> — рассылка всем доступным\n"
                "/key <ключ> — активировать ключ (пользовательская команда)\n")
    else:
        text = ("Меню:\n"
                "/start — проверка\n"
                "/key <ключ> — активировать временный доступ\n"
                "Если у тебя есть доступ — используй основные команды бота.")
    bot.send_message(uid, text)

# Admin: add
@bot.message_handler(commands=['add'])
def cmd_add(message):
    uid = message.from_user.id
    if not is_admin(uid):
        bot.reply_to(message, "Только владелец может выдавать доступ.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "Использование: /add <user_id>")
        return
    try:
        target = int(parts[1])
    except:
        bot.reply_to(message, "Неверный ID.")
        return
    with storage_lock:
        allowed_users.add(target)
    bot.reply_to(message, f"✅ Пользователь {target} получил доступ.")

# Admin: remove
@bot.message_handler(commands=['remove'])
def cmd_remove(message):
    uid = message.from_user.id
    if not is_admin(uid):
        bot.reply_to(message, "Только владелец может убирать доступ.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "Использование: /remove <user_id>")
        return
    try:
        target = int(parts[1])
    except:
        bot.reply_to(message, "Неверный ID.")
        return
    with storage_lock:
        if target in allowed_users:
            allowed_users.remove(target)
            bot.reply_to(message, f"✅ Доступ у {target} удалён.")
        else:
            bot.reply_to(message, "Пользователь не в списке доступа.")

# Admin: list users
@bot.message_handler(commands=['users'])
def cmd_users(message):
    uid = message.from_user.id
    if not is_admin(uid):
        bot.reply_to(message, "Только владелец может смотреть список пользователей.")
        return
    with storage_lock:
        if not allowed_users:
            bot.reply_to(message, "Список пуст.")
            return
        text = "Пользователи с доступом:\n" + "\n".join(str(x) for x in sorted(allowed_users))
    bot.reply_to(message, text)

# Admin: broadcast
@bot.message_handler(commands=['broadcast'])
def cmd_broadcast(message):
    uid = message.from_user.id
    if not is_admin(uid):
        bot.reply_to(message, "Только владелец может рассылать.")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Использование: /broadcast <текст>")
        return
    text = parts[1]
    with storage_lock:
        targets = list(allowed_users)
    success = 0
    for t in targets:
        try:
            bot.send_message(t, text)
            success += 1
        except Exception:
            pass
    bot.reply_to(message, f"📬 Рассылка завершена. Отправлено: {success}/{len(targets)}")

# Admin: genkey
@bot.message_handler(commands=['genkey'])
def cmd_genkey(message):
    uid = message.from_user.id
    if not is_admin(uid):
        bot.reply_to(message, "Только владелец может генерировать ключи.")
        return
    k = generate_key()
    bot.reply_to(message, f"🔑 Ключ: `{k}`\nСрок: 6 часов, 1 использование.\nКоманда для активации: /key {k}", parse_mode='Markdown')

# Admin: revoke key
@bot.message_handler(commands=['revoke_key'])
def cmd_revoke_key(message):
    uid = message.from_user.id
    if not is_admin(uid):
        bot.reply_to(message, "Только владелец может отзывать ключи.")
        return
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "Использование: /revoke_key <ключ>")
        return
    k = parts[1].strip()
    with storage_lock:
        if k in keys:
            keys.pop(k, None)
            bot.reply_to(message, f"Ключ {k} отозван.")
        else:
            bot.reply_to(message, "Ключ не найден или уже истёк.")

# User: activate key
@bot.message_handler(commands=['key'])
def cmd_key(message):
    uid = message.from_user.id
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "Использование: /key <ключ>")
        return
    k = parts[1].strip()
    with storage_lock:
        entry = keys.get(k)
        if not entry:
            bot.reply_to(message, "❌ Неверный или просроченный ключ.")
            return
        # attempts check
        if entry['attempts'] >= KEY_MAX_ATTEMPTS:
            bot.reply_to(message, "❌ Превышено число попыток для этого ключа.")
            # можно удалить ключ
            keys.pop(k, None)
            return
        # valid -> consume
        entry['attempts'] += 1
        if time.time() - entry['created'] > KEY_TTL_SECONDS:
            keys.pop(k, None)
            bot.reply_to(message, "❌ Ключ истёк.")
            return
        if entry['uses_left'] <= 0:
            keys.pop(k, None)
            bot.reply_to(message, "❌ Ключ уже использован.")
            return
        # give access
        entry['uses_left'] -= 1
        allowed_users.add(uid)
        bot.reply_to(message, "✅ Ключ принят. У тебя временный доступ.")
        # если uses_left ==0 — удалить ключ
        if entry['uses_left'] <= 0:
            keys.pop(k, None)

# Example of a protected command (keeps old functionality)
@bot.message_handler(commands=['protected'])
def cmd_protected(message):
    uid = message.from_user.id
    if uid not in allowed_users:
        bot.reply_to(message, "У тебя нет доступа к этой команде. Попроси админа /key <ключ> или получить доступ.")
        return
    bot.reply_to(message, "Выполняю защищённую функцию... (старый функционал)")

# --- Webhook / Flask endpoints ---
@server.route('/', methods=['GET'])
def index():
    return "Bot is running", 200

@server.route('/', methods=['POST'])
def webhook_view():
    # Telegram posts updates here
    try:
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
    except Exception as e:
        # log exception if needed
        print("Webhook processing error:", e)
    return '', 200

# --- Start background cleanup thread ---
cleanup_thread = threading.Thread(target=cleanup_expired_keys, daemon=True)
cleanup_thread.start()

# --- Set webhook (remove previous, set new) ---
# IMPORTANT: WEBHOOK_URL must be accessible and valid for Telegram (https).
try:
    bot.remove_webhook()
    # small sleep to ensure Telegram processes remove_webhook
    time.sleep(0.5)
    bot.set_webhook(url=WEBHOOK_URL)
    print("Webhook set to:", WEBHOOK_URL)
except Exception as e:
    print("Error setting webhook:", e)

# --- Run Flask ---
if __name__ == "__main__":
    # Render will run the app. On local run:
    server.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

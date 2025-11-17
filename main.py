# main.py
import os
import time
import sqlite3
import secrets
from datetime import datetime, timedelta

from flask import Flask, request, jsonify
import telebot
from telebot import types

# -------- CONFIG from env --------
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")   # например https://your-domain.com/webhook
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

if not TOKEN:
    raise RuntimeError("Error: BOT_TOKEN not set in environment")
if not WEBHOOK_URL:
    raise RuntimeError("Error: WEBHOOK_URL not set in environment")
if OWNER_ID == 0:
    raise RuntimeError("Error: OWNER_ID not set in environment")

# -------- Bot & Flask app --------
bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

# -------- Database (SQLite) --------
DB_PATH = "bot.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            tg_id INTEGER PRIMARY KEY,
            is_admin INTEGER DEFAULT 0,
            added_at INTEGER
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS keys (
            key TEXT PRIMARY KEY,
            owner_id INTEGER,
            created_at INTEGER,
            expires_at INTEGER,
            max_uses INTEGER,
            uses INTEGER DEFAULT 0,
            max_attempts INTEGER DEFAULT 5,
            attempts INTEGER DEFAULT 0
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER,
            action TEXT,
            ts INTEGER
        )
        """)
        # Ensure owner exists as admin
        cur.execute("INSERT OR IGNORE INTO users (tg_id, is_admin, added_at) VALUES (?,?,?)",
                    (OWNER_ID, 1, int(time.time())))
        conn.commit()

def add_log(tg_id, action):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO logs (tg_id, action, ts) VALUES (?,?,?)", (tg_id, action, int(time.time())))
        conn.commit()

def is_user_allowed(tg_id):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT is_admin FROM users WHERE tg_id=?", (tg_id,))
        row = cur.fetchone()
        return row is not None

def is_admin(tg_id):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT is_admin FROM users WHERE tg_id=?", (tg_id,))
        r = cur.fetchone()
        return (r is not None and r[0] == 1) or tg_id == OWNER_ID

# -------- Key system --------
def gen_key(duration_minutes=60, max_uses=1, max_attempts=5):
    key = secrets.token_urlsafe(12)
    now = int(time.time())
    expires = now + duration_minutes * 60
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO keys (key, owner_id, created_at, expires_at, max_uses, uses, max_attempts, attempts) VALUES (?,?,?,?,?,?,?,?)",
                     (key, OWNER_ID, now, expires, max_uses, 0, max_attempts, 0))
        conn.commit()
    return key, expires

def use_key_for_user(key, tg_id):
    now = int(time.time())
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT expires_at, max_uses, uses, max_attempts, attempts FROM keys WHERE key=?", (key,))
        row = cur.fetchone()
        if not row:
            return False, "Key not found"
        expires_at, max_uses, uses, max_attempts, attempts = row
        if now > expires_at:
            return False, "Key expired"
        if uses >= max_uses:
            return False, "Key already used maximum times"
        if attempts >= max_attempts:
            return False, "Key blocked due to too many attempts"
        # mark use
        uses += 1
        cur.execute("UPDATE keys SET uses=? WHERE key=?", (uses, key))
        # give user access
        cur.execute("INSERT OR REPLACE INTO users (tg_id, is_admin, added_at) VALUES (?,?,?)", (tg_id, 0, now))
        conn.commit()
        add_log(tg_id, f"used_key:{key}")
        return True, "Access granted"

def record_key_attempt(key):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE keys SET attempts = attempts + 1 WHERE key=?", (key,))
        conn.commit()

# -------- Bot UI (keyboards) --------
def main_menu_keyboard(tg_id):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("ℹ️ Help", callback_data="help"))
    kb.add(types.InlineKeyboardButton("🔑 Use key (/usekey)", callback_data="usekey"))
    kb.add(types.InlineKeyboardButton("🆕 Get temp key", callback_data="getkey"))
    if is_admin(tg_id):
        kb.add(types.InlineKeyboardButton("🛠 Admin panel", callback_data="admin_panel"))
        kb.add(types.InlineKeyboardButton("📣 Broadcast", callback_data="broadcast"))
    return kb

def admin_panel_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("➕ Add user (/add)", callback_data="admin_add"))
    kb.add(types.InlineKeyboardButton("➖ Remove user (/remove)", callback_data="admin_remove"))
    kb.add(types.InlineKeyboardButton("🔑 Gen key (/genkey)", callback_data="admin_genkey"))
    kb.add(types.InlineKeyboardButton("👥 Users list (/users)", callback_data="admin_users"))
    kb.add(types.InlineKeyboardButton("⬅️ Back", callback_data="back"))
    return kb

# -------- Bot commands --------
@bot.message_handler(commands=["start"])
def cmd_start(message):
    txt = f"👋 Привет, {message.from_user.first_name}!\n\n" \
          f"Добро пожаловать в *{os.getenv('BOT_NAME','MetaSnos')}* 🤖\n\n" \
          "Нажми на кнопку ниже, чтобы открыть меню."
    add_log(message.from_user.id, "start")
    bot.send_message(message.chat.id, txt, parse_mode="Markdown", reply_markup=main_menu_keyboard(message.from_user.id))

@bot.message_handler(commands=["menu"])
def cmd_menu(message):
    bot.send_message(message.chat.id, "Меню:", reply_markup=main_menu_keyboard(message.from_user.id))

@bot.message_handler(commands=["add"])
def cmd_add(message):
    if not is_admin(message.from_user.id):
        return bot.reply_to(message, "❌ Только администратор может добавлять пользователей.")
    parts = message.text.split()
    if len(parts) < 2:
        return bot.reply_to(message, "Использование: /add <user_id>")
    try:
        uid = int(parts[1])
    except:
        return bot.reply_to(message, "Неверный ID.")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT OR REPLACE INTO users (tg_id, is_admin, added_at) VALUES (?,?,?)", (uid, 0, int(time.time())))
        conn.commit()
    add_log(message.from_user.id, f"add_user:{uid}")
    bot.reply_to(message, f"✅ Пользователь {uid} получил доступ.")

@bot.message_handler(commands=["remove"])
def cmd_remove(message):
    if not is_admin(message.from_user.id):
        return bot.reply_to(message, "❌ Только админ может удалять доступ.")
    parts = message.text.split()
    if len(parts) < 2:
        return bot.reply_to(message, "Использование: /remove <user_id>")
    try:
        uid = int(parts[1])
    except:
        return bot.reply_to(message, "Неверный ID.")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM users WHERE tg_id=?", (uid,))
        conn.commit()
    add_log(message.from_user.id, f"remove_user:{uid}")
    bot.reply_to(message, f"✅ Доступ удалён у {uid}")

@bot.message_handler(commands=["users"])
def cmd_users(message):
    if not is_admin(message.from_user.id):
        return bot.reply_to(message, "❌ Только админ может смотреть список пользователей.")
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT tg_id, is_admin, added_at FROM users")
        rows = cur.fetchall()
    text = "👥 Пользователи:\n"
    for r in rows:
        uid, isadm, at = r
        text += f"- {uid} {'(admin)' if isadm else ''}\n"
    bot.reply_to(message, text)

@bot.message_handler(commands=["genkey"])
def cmd_genkey(message):
    if not is_admin(message.from_user.id):
        return bot.reply_to(message, "❌ Только админ может генерировать ключи.")
    parts = message.text.split()
    # default: 60 minutes, 1 use
    minutes = 60
    uses = 1
    attempts = 5
    if len(parts) >= 2:
        try:
            minutes = int(parts[1])
        except:
            pass
    if len(parts) >= 3:
        try:
            uses = int(parts[2])
        except:
            pass
    if len(parts) >= 4:
        try:
            attempts = int(parts[3])
        except:
            pass
    key, expires = gen_key(minutes, uses, attempts)
    dt = datetime.utcfromtimestamp(expires).strftime('%Y-%m-%d %H:%M:%S UTC')
    bot.reply_to(message, f"🔐 Ключ: `{key}`\nИстекает: {dt}\nМакс использований: {uses}\nМакс попыток: {attempts}", parse_mode="Markdown")
    add_log(message.from_user.id, f"genkey:{key}")

@bot.message_handler(commands=["usekey"])
def cmd_usekey(message):
    parts = message.text.split()
    if len(parts) < 2:
        return bot.reply_to(message, "Использование: /usekey <key>")
    key = parts[1].strip()
    ok, reason = use_key_for_user(key, message.from_user.id)
    if ok:
        bot.reply_to(message, "✅ Ключ принят, доступ выдан.")
    else:
        # record attempt
        record_key_attempt(key)
        bot.reply_to(message, f"❌ {reason}")

@bot.message_handler(commands=["broadcast"])
def cmd_broadcast(message):
    if not is_admin(message.from_user.id):
        return bot.reply_to(message, "❌ Только админ может запускать рассылки.")
    text = message.text.partition(' ')[2].strip()
    if not text:
        return bot.reply_to(message, "Использование: /broadcast <текст рассылки>")
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT tg_id FROM users")
        rows = cur.fetchall()
    sent = 0
    for (uid,) in rows:
        try:
            bot.send_message(uid, text)
            sent += 1
        except Exception as e:
            # skip blocked users
            pass
    bot.reply_to(message, f"📣 Рассылка завершена. Отправлено: {sent}")
    add_log(message.from_user.id, f"broadcast_sent:{sent}")

# -------- Callback query handlers for inline keyboard --------
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    user_id = call.from_user.id
    data = call.data
    if data == "help":
        bot.answer_callback_query(call.id, "Справка")
        bot.send_message(call.message.chat.id, "Помощь: используй /menu и кнопки.\nКоманды:\n/add /remove /users /genkey /usekey /broadcast")
    elif data == "usekey":
        bot.answer_callback_query(call.id, "Введите командой: /usekey <ключ>")
        bot.send_message(call.message.chat.id, "Введите командой: /usekey <ключ>")
    elif data == "getkey":
        bot.answer_callback_query(call.id, "Запрос ключа")
        bot.send_message(call.message.chat.id, "Чтобы получить ключ — попросите администратора сгенерировать /genkey")
    elif data == "admin_panel":
        if not is_admin(user_id):
            return bot.answer_callback_query(call.id, "Недоступно")
        bot.edit_message_text("🔐 Админ-панель:", call.message.chat.id, call.message.message_id, reply_markup=admin_panel_keyboard())
    elif data == "admin_add":
        bot.answer_callback_query(call.id, "Используй команду: /add <user_id>")
        bot.send_message(call.message.chat.id, "Использование: /add <user_id>")
    elif data == "admin_remove":
        bot.answer_callback_query(call.id, "Используй команду: /remove <user_id>")
        bot.send_message(call.message.chat.id, "Использование: /remove <user_id>")
    elif data == "admin_genkey":
        bot.answer_callback_query(call.id, "Используй команду: /genkey <minutes> <uses> <attempts>")
        bot.send_message(call.message.chat.id, "Пример: /genkey 60 1 5  — ключ 60 минут, 1 использование, 5 попыток")
    elif data == "admin_users":
        if not is_admin(user_id):
            return bot.answer_callback_query(call.id, "Недоступно")
        # show users
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("SELECT tg_id FROM users")
            rows = cur.fetchall()
        text = "Пользователи:\n" + "\n".join(str(r[0]) for r in rows)
        bot.send_message(call.message.chat.id, text)
    elif data == "back":
        bot.edit_message_text("Меню:", call.message.chat.id, call.message.message_id, reply_markup=main_menu_keyboard(user_id))
    elif data == "broadcast":
        bot.answer_callback_query(call.id, "Чтобы сделать рассылку: /broadcast <текст>")
        bot.send_message(call.message.chat.id, "Использование: /broadcast <текст>")

# -------- Webhook route --------
@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    # Telegram will POST updates here
    try:
        json_str = request.get_data().decode("utf-8")
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
    except Exception as e:
        # log exception
        print("Webhook processing error:", e)
    return jsonify({"ok": True})

@app.route("/")
def index():
    return "Bot is running."

# -------- Set webhook when app starts on Render --------
def set_webhook():
    # final webhook path should be WEBHOOK_URL + /webhook/<token>
    full = WEBHOOK_URL.rstrip("/") + f"/webhook/{TOKEN}"
    try:
        bot.remove_webhook()
    except Exception:
        pass
    ok = bot.set_webhook(url=full)
    if not ok:
        raise RuntimeError("Failed to set webhook to: " + full)
    print("Webhook set to", full)
    add_log(OWNER_ID, f"webhook_set:{full}")

# -------- App entrypoint for Gunicorn --------
if __name__ == "__main__":
    init_db()
    set_webhook()
    # when run locally for testing, use Flask built-in
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
else:
    # when loaded by gunicorn on Render
    init_db()
    set_webhook()

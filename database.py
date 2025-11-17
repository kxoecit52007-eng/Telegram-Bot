import sqlite3

DB_NAME = "bot.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            access INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS keys (
            key TEXT PRIMARY KEY,
            activated INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


def add_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()


def user_has_access(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT access FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row and row[0] == 1


def activate_key(user_id, key):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("SELECT activated FROM keys WHERE key=?", (key,))
    row = c.fetchone()

    if not row:
        conn.close()
        return "❌ Ключ не найден!"

    if row[0] == 1:
        conn.close()
        return "⚠ Ключ уже активирован!"

    c.execute("UPDATE users SET access=1 WHERE user_id=?", (user_id,))
    c.execute("UPDATE keys SET activated=1 WHERE key=?", (key,))
    conn.commit()
    conn.close()

    return "🔑 Доступ успешно активирован! Добро пожаловать!"


def create_key(key):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO keys (key) VALUES (?)", (key,))
    conn.commit()
    conn.close()


def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = c.fetchall()
    conn.close()
    return users

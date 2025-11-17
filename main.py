import os
import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram import Router
from fastapi import FastAPI, Request
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

# ==============================
# 📌 Переменные окружения
# ==============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# ==============================
# 📌 База данных
# ==============================
db = sqlite3.connect("database.db")
sql = db.cursor()

sql.execute("""CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY
)""")

sql.execute("""CREATE TABLE IF NOT EXISTS access_keys(
    key TEXT PRIMARY KEY,
    is_used INTEGER DEFAULT 0
)""")

db.commit()

# ==============================
# 📌 Диспетчер и FastAPI
# ==============================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
app = FastAPI()

# ==============================
# 📌 Кнопки меню
# ==============================
user_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💎 Получить доступ")],
        [KeyboardButton(text="ℹ️ Помощь")]
    ],
    resize_keyboard=True
)

admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🗝 Создать ключ")],
        [KeyboardButton(text="📜 Список ключей"), KeyboardButton(text="🧹 Удалить ключ")],
        [KeyboardButton(text="👥 Список пользователей")],
        [KeyboardButton(text="📨 Рассылка")],
        [KeyboardButton(text="🏠 Главное меню")]
    ],
    resize_keyboard=True
)

# ==============================
# 📌 Старт / Приветствие
# ==============================
@router.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    sql.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    db.commit()

    text = (
        "👋 <b>Привет!</b>\n\n"
        "Ты попал в бота <b>MetaSnos</b> ⚡\n"
        "Чтобы получить доступ — используй специальный ключ 🔑"
    )

    if user_id == OWNER_ID:
        await message.answer("👑 Добро пожаловать, создатель!", reply_markup=admin_menu)
    else:
        await message.answer(text, reply_markup=user_menu, parse_mode=ParseMode.HTML)

# ==============================
# 📌 Ввод ключа
# ==============================
@router.message(F.text == "💎 Получить доступ")
async def ask_key(message: types.Message):
    await message.answer("🔑 Введите ваш ключ доступа:")

@router.message()
async def check_key(message: types.Message):
    user_id = message.from_user.id
    key = message.text.strip()

    sql.execute("SELECT is_used FROM access_keys WHERE key = ?", (key,))
    res = sql.fetchone()

    if res is None:
        return

    if res[0] == 1:
        await message.answer("⛔ Этот ключ уже использовали.")
        return

    sql.execute("UPDATE access_keys SET is_used = 1 WHERE key = ?", (key,))
    db.commit()
    await message.answer("✅ Доступ успешно активирован!")

# ==============================
# 📌 Админ: создание ключа
# ==============================
@router.message(F.text == "🗝 Создать ключ")
async def generate_key(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return

    import secrets
    new_key = secrets.token_hex(4)
    sql.execute("INSERT INTO access_keys (key) VALUES (?)", (new_key,))
    db.commit()
    await message.answer(f"🆕 Новый ключ:\n<code>{new_key}</code>", parse_mode=ParseMode.HTML)

# ==============================
# 📌 Webhook обработчик
# ==============================
@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
    return {"status": "ok"}

# ==============================
# 📌 Запуск
# ==============================
async def main():
    await bot.set_webhook(WEBHOOK_URL)
    dp.include_router(router)
    print("Bot started with Webhook!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

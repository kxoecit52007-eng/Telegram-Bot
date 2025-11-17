import json
import asyncio
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.utils.markdown import hbold
from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
BOT_NAME = os.getenv("BOT_NAME", "Bot")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()

DB_FILE = "database.json"

# ========= Database ========= #
def load_db():
    if not os.path.exists(DB_FILE):
        save_db({"users": {}, "keys": {}})
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=4)

# ========= UI Keyboards ========= #
def main_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Ввести ключ", callback_data="enter_key")],
        [InlineKeyboardButton(text="📩 Поддержка", url="https://t.me/kxoecit52007")]
    ])
    return kb

def admin_panel():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать ключ", callback_data="generate_key")],
        [InlineKeyboardButton(text="📨 Рассылка", callback_data="broadcast")],
        [InlineKeyboardButton(text="📋 Список ключей", callback_data="list_keys")]
    ])
    return kb

# ========= Handlers ========= #
@dp.message(CommandStart())
async def start(message: Message):
    user_id = str(message.from_user.id)
    db = load_db()

    if user_id not in db["users"]:
        db["users"][user_id] = {"access": False}
        save_db(db)

    text = f"👋 Привет, {hbold(message.from_user.first_name)}!\n" \
           f"Я — {hbold(BOT_NAME)} 🤖\n\n" \
           f"Чтобы получить доступ, нажми кнопку ниже ⬇️"
    await message.answer(text, reply_markup=main_menu(), parse_mode=ParseMode.HTML)

@dp.callback_query(lambda c: c.data == "enter_key")
async def ask_key(call):
    await call.message.answer("🔑 Введи ключ доступа:")
    await call.answer()

@dp.message()
async def key_handler(message: Message):
    user_id = str(message.from_user.id)
    db = load_db()

    # Admin access
    if message.from_user.id == OWNER_ID and message.text == "/admin":
        return await message.answer("👑 Админ панель", reply_markup=admin_panel())

    # Key validation
    key = message.text.strip()
    if key in db["keys"] and db["keys"][key]["uses"] > 0:
        db["keys"][key]["uses"] -= 1
        db["users"][user_id]["access"] = True
        save_db(db)
        return await message.answer("✅ Доступ активирован!")

    await message.answer("❌ Неверный или израсходованный ключ.")

# ========= Admin Features ========= #
@dp.callback_query(lambda c: c.data == "generate_key")
async def generate_key(call):
    if call.from_user.id != OWNER_ID:
        return await call.answer("⛔ Нет доступа")
    import secrets
    key = secrets.token_hex(4)
    db = load_db()
    db["keys"][key] = {"uses": 3}
    save_db(db)
    await call.message.answer(f"🔑 Ключ создан:\n`{key}`", parse_mode="Markdown")

@dp.callback_query(lambda c: c.data == "list_keys")
async def list_keys(call):
    if call.from_user.id != OWNER_ID:
        return await call.answer("⛔ Нет доступа")
    db = load_db()
    txt = "📋 Список ключей:\n\n"
    for key, data in db["keys"].items():
        txt += f"`{key}` — Осталось: {data['uses']}\n"
    await call.message.answer(txt, parse_mode="Markdown")

@dp.callback_query(lambda c: c.data == "broadcast")
async def ask_broadcast(call):
    if call.from_user.id != OWNER_ID:
        return await call.answer("⛔ Нет доступа")
    await call.message.answer("✍️ Введи текст для рассылки:")
    dp.chat_broadcast = call.from_user.id

@dp.message()
async def broadcast(message: Message):
    if getattr(dp, "chat_broadcast", None) == message.from_user.id:
        db = load_db()
        sent = 0
        for uid in db["users"]:
            try:
                await bot.send_message(uid, message.text)
                sent += 1
            except:
                pass
        dp.chat_broadcast = None
        await message.answer(f"📨 Рассылка завершена.\nОтправлено: {sent}")

# ========= Webhook ========= #
@app.post("/webhook")
async def webhook(request: Request):
    update = await request.json()
    await dp.feed_update(bot, update)
    return {"status": "ok"}

@app.on_event("startup")
async def on_startup():
    try:
        await bot.set_webhook(WEBHOOK_URL)
        print(f"Webhook установлен: {WEBHOOK_URL}")
    except Exception as e:
        print("Ошибка вебхука:", e)

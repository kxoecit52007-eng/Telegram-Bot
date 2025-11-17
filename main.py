import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import os

TOKEN = os.getenv("BOT_TOKEN")  # токен из Render
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))  # твой Telegram ID
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # URL Render

# Хранилище ключей и активных пользователей (можно заменить на БД)
access_keys = {"TEST-123": True}
allowed_users = set()

# Логирование
logging.basicConfig(level=logging.INFO)

# Главное меню
def main_menu():
    keyboard = [
        [InlineKeyboardButton("📌 Моя панель", callback_data="panel")],
        [InlineKeyboardButton("🔑 Ввести ключ", callback_data="key")],
    ]
    return InlineKeyboardMarkup(keyboard)

# Админ меню
def admin_menu():
    keyboard = [
        [InlineKeyboardButton("👥 Пользователи", callback_data="users")],
        [InlineKeyboardButton("📨 Рассылка", callback_data="broadcast")],
        [InlineKeyboardButton("➕ Добавить ключ", callback_data="add_key")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ====================== Команды ======================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Добро пожаловать в закрытую систему доступа.\n"
        "Чтобы пользоваться ботом — введи ключ доступа 🔑",
        reply_markup=main_menu()
    )

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return await update.message.reply_text("⛔ Нет доступа!")

    await update.message.reply_text("👑 Админ панель:", reply_markup=admin_menu())


# ==================== Обработка Кнопок ====================

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id

    # Ввести ключ
    if query.data == "key":
        context.user_data["await_key"] = True
        return await query.edit_message_text("🔑 Введи ключ:")

    # Панель пользователя
    if query.data == "panel":
        if uid not in allowed_users:
            return await query.edit_message_text("⛔ У тебя нет доступа. Введи ключ.")
        return await query.edit_message_text("📌 Твоя панель. Функции будут тут позже.")

    # Админ кнопки
    if uid == ADMIN_ID:

        if query.data == "users":
            return await query.edit_message_text(f"👥 Пользователи:\n{allowed_users}")

        if query.data == "add_key":
            context.user_data["await_new_key"] = True
            return await query.edit_message_text("Введите новый ключ для добавления:")

        if query.data == "broadcast":
            context.user_data["await_broadcast"] = True
            return await query.edit_message_text("Введите текст рассылки:")

    else:
        return await query.edit_message_text("⛔ Нет доступа!")


# ==================== Сообщения текста ====================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.message.from_user.id

    # Обработка ключа
    if context.user_data.get("await_key"):
        context.user_data["await_key"] = False

        if text in access_keys:
            allowed_users.add(uid)
            return await update.message.reply_text("🔓 Доступ открыт! Можешь пользоваться ботом.", reply_markup=main_menu())
        else:
            return await update.message.reply_text("⛔ Неверный ключ!")

    # Добавление ключа админом
    if context.user_data.get("await_new_key") and uid == ADMIN_ID:
        context.user_data["await_new_key"] = False
        access_keys[text] = True
        return await update.message.reply_text(f"✅ Новый ключ добавлен: {text}")

    # Рассылка
    if context.user_data.get("await_broadcast") and uid == ADMIN_ID:
        context.user_data["await_broadcast"] = False
        msg = text
        for user in allowed_users:
            try:
                await context.bot.send_message(user, f"📢 Рассылка:\n{msg}")
            except:
                pass
        return await update.message.reply_text("📨 Рассылка завершена!")

    await update.message.reply_text("Не понимаю, воспользуйся меню ↓", reply_markup=main_menu())


# ==================== Запуск Webhook ====================

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.TEXT, handle_text))

    await app.start()
    await app.bot.set_webhook(WEBHOOK_URL)
    await app.idle()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

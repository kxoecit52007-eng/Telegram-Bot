import os
from aiogram import Bot, Dispatcher, types
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
import httpx

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

async def ask_openai(user_text: str) -> str:
    """
    Отправляет запрос к OpenAI Chat Completions
    """
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "gpt-4o-mini",   # можешь заменить на gpt-4o или gpt-4.1
        "messages": [
            {"role": "system", "content": "Ты - полезный умный Telegram-бот."},
            {"role": "user", "content": user_text}
        ],
        "temperature": 0.7
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(url, json=payload, headers=headers)

    if r.status_code != 200:
        return f"Ошибка OpenAI: {r.text}"

    data = r.json()
    reply = data["choices"][0]["message"]["content"]
    return reply


@dp.message()
async def handle_message(message: types.Message):
    user_text = message.text

    await message.answer("💬 Думаю...")

    reply = await ask_openai(user_text)

    await message.answer(reply)


async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(app):
    await bot.delete_webhook()
    await bot.session.close()

def main():
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        handle_in_background=True
    ).register(app, path="/webhook")

    return app

if __name__ == "__main__":
    web.run_app(main(), host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

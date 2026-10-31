import asyncio
import logging
import os
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiohttp import web

from config import BOT_TOKEN
from database import init_db
from handlers import router
from web_admin import create_admin_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

async def main():
    if not BOT_TOKEN:
        logger.error("XATOLIK: .env faylida BOT_TOKEN ko'rsatilmagan! Iltimos, BOT_TOKEN ni kiriting.")
        return

    # 1. Ma'lumotlar bazasini tayyorlash
    await init_db()
    logger.info("Ma'lumotlar bazasi tayyorlandi.")

    # 2. Web Admin panelni fonda ishga tushirish (Railway portini qo'llab-quvvatlaydi)
    port = int(os.getenv("PORT", "8080"))
    admin_app = create_admin_app()
    app_runner = web.AppRunner(admin_app)
    await app_runner.setup()
    site = web.TCPSite(app_runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🚀 Web Admin Panel ishga tushdi: port {port}")

    # 3. Telegram Botni ishga tushirish
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    dp = Dispatcher()
    dp.include_router(router)

    logger.info("🤖 Telegram Bot ishga tushmoqda...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(
            bot,
            allowed_updates=["message", "callback_query", "chat_member", "my_chat_member"]
        )
    finally:
        await app_runner.cleanup()
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Dastur to'xtatildi.")


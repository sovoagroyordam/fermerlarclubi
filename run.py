import asyncio
import logging
import os
import sys
import aiohttp
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

async def keep_alive_task():
    """
    Render yoki shunga o'xshash bepul serverlarda container 15 daqiqada uxlab qolmasligi uchun
    har 10 daqiqada RENDER_EXTERNAL_URL yoki PING_URL ga ping yuborib turadi.
    """
    await asyncio.sleep(60)  # Server to'liq yuklanguncha 1 daqiqa kutish
    url = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("PING_URL")
    if not url:
        logger.info("ℹ️ RENDER_EXTERNAL_URL topilmadi. Agar Renderda bo'lsangiz, tashqi ping xizmatidan (masalan, UptimeRobot) foydalaning.")
        return

    health_url = url.rstrip("/") + "/health"
    logger.info(f"🔄 Render Keep-Alive fon xizmati faollashdi: {health_url}")

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(health_url, timeout=15) as resp:
                    logger.info(f"💓 Keep-alive ping: {health_url} -> Status {resp.status}")
            except Exception as e:
                logger.warning(f"⚠️ Keep-alive ping xatosi: {e}")
            await asyncio.sleep(600)  # Har 10 daqiqada (Render 15 daqiqada uxlaydi)

async def main():
    if not BOT_TOKEN:
        logger.error("XATOLIK: .env faylida BOT_TOKEN ko'rsatilmagan! Iltimos, BOT_TOKEN ni kiriting.")
        return

    # 1. Ma'lumotlar bazasini tayyorlash
    await init_db()
    logger.info("Ma'lumotlar bazasi tayyorlandi.")

    # 2. Web Admin panelni fonda ishga tushirish (Render / Railway PORT o'zgaruvchisini qo'llab-quvvatlaydi)
    port = int(os.getenv("PORT", "8080"))
    admin_app = create_admin_app()
    app_runner = web.AppRunner(admin_app)
    await app_runner.setup()
    site = web.TCPSite(app_runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🚀 Web Admin Panel ishga tushdi: port {port}")

    # 3. Render Keep-Alive vazifasini fonda ishga tushirish
    keep_alive_fut = asyncio.create_task(keep_alive_task())

    # 4. Telegram Botni ishga tushirish
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
        keep_alive_fut.cancel()
        await app_runner.cleanup()
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Dastur to'xtatildi.")


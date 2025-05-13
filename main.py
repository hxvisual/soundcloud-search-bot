import asyncio
import logging
import sys
import os
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN
from handlers import router
from utils.logger import setup_root_logger, setup_logger

setup_root_logger(log_to_file=False)
logger = setup_logger(__name__, log_to_file=False)

async def main():
    if not BOT_TOKEN:
        logger.error("No token provided. Set BOT_TOKEN environment variable.")
        return
    
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    
    dp = Dispatcher(storage=MemoryStorage())
    
    dp.include_router(router)
    
    await bot.delete_webhook(drop_pending_updates=True)
    
    try:
        logger.info("Starting SoundCloud Bot")
        await dp.start_polling(bot)
    finally:
        logger.info("Bot stopped!")
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped manually!")
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True)
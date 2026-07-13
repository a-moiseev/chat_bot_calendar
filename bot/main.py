"""Точка входа бота."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot import config
from bot.db import init_db
from bot.handlers import admin, broadcast, start
from bot.health import health, start_health_server
from bot.scheduler import start_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


async def main() -> None:
    config.validate()
    config.get_welcome_text()  # упасть на старте, если нет welcome.html
    await init_db()

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(admin.router)
    dp.include_router(broadcast.router)
    dp.include_router(start.router)

    me = await bot.get_me()  # упасть на старте, если токен не рабочий
    health.tick("telegram")
    logger.info("Бот @%s запущен", me.username)

    scheduler = start_scheduler(bot)

    await bot.delete_webhook(drop_pending_updates=True)
    polling = asyncio.create_task(dp.start_polling(bot))
    health.watch(polling=polling, scheduler=scheduler)
    runner = await start_health_server()

    try:
        await polling
    finally:
        await runner.cleanup()
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())

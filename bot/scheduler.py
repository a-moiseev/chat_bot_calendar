"""Планировщик отложенных рассылок: ежеминутный опрос БД."""

from __future__ import annotations

import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot import db
from bot.broadcaster import BroadcastPayload, broadcast_to_all
from bot.timeutils import MOSCOW_TZ, now_str

logger = logging.getLogger(__name__)


async def _process_due(bot: Bot) -> None:
    for row in await db.get_due(now_str()):
        payload = BroadcastPayload.from_scheduled(row)
        sent, failed = await broadcast_to_all(bot, payload)
        await db.mark_sent(row.id)
        logger.info(
            "Отложенная рассылка #%s отправлена: %s, ошибок: %s", row.id, sent, failed
        )


def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)
    scheduler.add_job(
        _process_due,
        trigger="interval",
        minutes=1,
        args=(bot,),
        id="due_broadcasts",
    )
    scheduler.start()
    return scheduler

"""Планировщик отложенных рассылок: ежеминутный опрос БД."""

from __future__ import annotations

import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot import db
from bot.broadcaster import BroadcastPayload, broadcast_to_all
from bot.health import BROADCAST_JOB_ID, health
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


async def _heartbeat() -> None:
    health.tick("loop")


async def _ping_telegram(bot: Bot) -> None:
    try:
        await bot.get_me()
    except Exception:
        logger.warning("Telegram не ответил на getMe", exc_info=True)
    else:
        health.tick("telegram")


def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)
    scheduler.add_job(
        _process_due,
        trigger="interval",
        minutes=1,
        args=(bot,),
        id=BROADCAST_JOB_ID,
    )
    # отдельная задача, а не тик внутри _process_due: длинная рассылка занимает
    # единственный слот due_broadcasts (max_instances=1) и пульс бы пропадал
    scheduler.add_job(
        _heartbeat,
        trigger="interval",
        seconds=30,
        id="heartbeat",
    )
    scheduler.add_job(
        _ping_telegram,
        trigger="interval",
        minutes=5,
        args=(bot,),
        id="telegram_ping",
    )
    scheduler.start()
    return scheduler

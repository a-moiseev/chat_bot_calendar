"""Liveness probe: HTTP-эндпоинт /healthz для внешнего мониторинга."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from functools import partial
from typing import Any

from aiohttp import web
from apscheduler.schedulers.base import BaseScheduler

from bot import config

logger = logging.getLogger(__name__)

# Сколько терпим отсутствие пульса, прежде чем считать подсистему залипшей.
LOOP_STALE_SECONDS = 180  # heartbeat планировщика тикает раз в 30 с
# getMe идёт раз в 5 минут: лимит с запасом, чтобы пара сетевых сбоёв подряд не била тревогу
TELEGRAM_STALE_SECONDS = 900

BROADCAST_JOB_ID = "due_broadcasts"
TRACKED = (("loop", LOOP_STALE_SECONDS), ("telegram", TELEGRAM_STALE_SECONDS))


class Health:
    """Признаки жизни бота: event loop, связь с Telegram, polling, планировщик."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._started = clock()
        self._ticks: dict[str, float] = {}
        self._polling: asyncio.Task[Any] | None = None
        self._scheduler: BaseScheduler | None = None

    def tick(self, name: str) -> None:
        """Отметить, что подсистема подала признак жизни."""
        self._ticks[name] = self._clock()

    def watch(
        self,
        *,
        polling: asyncio.Task[Any] | None = None,
        scheduler: BaseScheduler | None = None,
    ) -> None:
        if polling is not None:
            self._polling = polling
        if scheduler is not None:
            self._scheduler = scheduler

    def check(self) -> tuple[bool, dict[str, Any]]:
        """Здоров ли бот и почему нет."""
        problems: list[str] = []

        if self._polling is not None and self._polling.done():
            problems.append("polling: цикл получения апдейтов остановлен")

        for name, limit in TRACKED:
            problem = self._stale(name, limit)
            if problem is not None:
                problems.append(problem)

        problem = self._broadcast_job_problem()
        if problem is not None:
            problems.append(problem)

        details: dict[str, Any] = {
            "status": "unhealthy" if problems else "ok",
            "uptime": int(self._clock() - self._started),
            "last_tick": {
                name: int(age)
                for name, _ in TRACKED
                if (age := self._age(name)) is not None
            },
        }
        if problems:
            details["problems"] = problems
        return not problems, details

    def _age(self, name: str) -> float | None:
        tick = self._ticks.get(name)
        return None if tick is None else self._clock() - tick

    def _stale(self, name: str, limit: float) -> str | None:
        age = self._age(name)
        if age is None:
            # пульса ещё не было: даём подсистеме на раскачку тот же лимит
            if self._clock() - self._started > limit:
                return f"{name}: пульса не было ни разу"
            return None
        if age > limit:
            return f"{name}: последний пульс {int(age)} с назад (лимит {int(limit)} с)"
        return None

    def _broadcast_job_problem(self) -> str | None:
        if self._scheduler is None:
            return None
        job = self._scheduler.get_job(BROADCAST_JOB_ID)
        if job is None:
            return "scheduler: задача отложенных рассылок не найдена"
        if job.next_run_time is None:
            return "scheduler: задача отложенных рассылок на паузе"
        return None


health = Health()
HEALTH_KEY: web.AppKey[Health] = web.AppKey("health")


async def _healthz(request: web.Request) -> web.Response:
    probe = request.app[HEALTH_KEY]
    ok, details = probe.check()
    if not ok:
        logger.warning("Liveness probe: %s", details["problems"])
    # ensure_ascii=False: причины по-русски, читаемо и в мониторинге, и в curl
    return web.json_response(
        details,
        status=200 if ok else 503,
        dumps=partial(json.dumps, ensure_ascii=False),
    )


def build_app(probe: Health) -> web.Application:
    app = web.Application()
    app[HEALTH_KEY] = probe
    app.router.add_get("/healthz", _healthz)
    return app


async def start_health_server(
    probe: Health | None = None, port: int | None = None
) -> web.AppRunner:
    """Поднять сервер с /healthz (access-лог выключен: мониторинг ходит часто)."""
    if probe is None:
        probe = health
    if port is None:
        port = config.HEALTH_PORT

    runner = web.AppRunner(build_app(probe), access_log=None)
    await runner.setup()
    await web.TCPSite(runner, host="0.0.0.0", port=port).start()
    logger.info("Liveness probe слушает 0.0.0.0:%s/healthz", port)
    return runner

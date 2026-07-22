"""Liveness probe: a /healthz HTTP endpoint for external monitoring."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

from aiohttp import web
from apscheduler.schedulers.base import BaseScheduler

from bot import config

logger = logging.getLogger(__name__)

# How long a subsystem may go without a heartbeat before we call it stuck.
LOOP_STALE_SECONDS = 180  # the scheduler heartbeat ticks every 30s
# getMe runs every 5 minutes; the slack keeps a couple of network blips from firing an alarm
TELEGRAM_STALE_SECONDS = 900

BROADCAST_JOB_ID = "due_broadcasts"
TRACKED = (("loop", LOOP_STALE_SECONDS), ("telegram", TELEGRAM_STALE_SECONDS))


class Health:
    """Signs of life: event loop, Telegram connectivity, polling, scheduler."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._started = clock()
        self._ticks: dict[str, float] = {}
        self._polling: asyncio.Task[Any] | None = None
        self._scheduler: BaseScheduler | None = None

    def tick(self, name: str) -> None:
        """Record that a subsystem reported a sign of life."""
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
        """Whether the bot is healthy, and if not, why."""
        problems: list[str] = []

        if self._polling is not None and self._polling.done():
            problems.append("polling: the update polling loop has stopped")

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
            # no heartbeat yet: allow the same limit as warm-up time
            if self._clock() - self._started > limit:
                return f"{name}: no heartbeat recorded yet"
            return None
        if age > limit:
            return f"{name}: last heartbeat {int(age)}s ago (limit {int(limit)}s)"
        return None

    def _broadcast_job_problem(self) -> str | None:
        if self._scheduler is None:
            return None
        job = self._scheduler.get_job(BROADCAST_JOB_ID)
        if job is None:
            return "scheduler: the scheduled-broadcast job is missing"
        if job.next_run_time is None:
            return "scheduler: the scheduled-broadcast job is paused"
        return None


health = Health()
HEALTH_KEY: web.AppKey[Health] = web.AppKey("health")


async def _healthz(request: web.Request) -> web.Response:
    probe = request.app[HEALTH_KEY]
    ok, details = probe.check()
    if not ok:
        logger.warning("Liveness probe: %s", details["problems"])
    return web.json_response(details, status=200 if ok else 503)


def build_app(probe: Health) -> web.Application:
    app = web.Application()
    app[HEALTH_KEY] = probe
    app.router.add_get("/healthz", _healthz)
    return app


async def start_health_server(
    probe: Health | None = None, port: int | None = None
) -> web.AppRunner:
    """Start the /healthz server (access log off: monitors poll frequently)."""
    if probe is None:
        probe = health
    if port is None:
        port = config.HEALTH_PORT

    runner = web.AppRunner(build_app(probe), access_log=None)
    await runner.setup()
    await web.TCPSite(runner, host="0.0.0.0", port=port).start()
    logger.info("Liveness probe listening on 0.0.0.0:%s/healthz", port)
    return runner

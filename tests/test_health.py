import asyncio

from aiohttp.test_utils import TestClient, TestServer

from bot import scheduler
from bot.health import (
    BROADCAST_JOB_ID,
    LOOP_STALE_SECONDS,
    TELEGRAM_STALE_SECONDS,
    Health,
    build_app,
)


class FakeClock:
    """Controllable clock in place of time.monotonic."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _alive(clock=None) -> Health:
    """A freshly started bot: every subsystem has a recent heartbeat."""
    probe = Health(clock=clock or FakeClock())
    probe.tick("loop")
    probe.tick("telegram")
    return probe


def test_fresh_ticks_are_healthy():
    ok, details = _alive().check()
    assert ok
    assert details["status"] == "ok"
    assert "problems" not in details


def test_stale_loop_tick_is_unhealthy():
    clock = FakeClock()
    probe = _alive(clock)
    clock.advance(LOOP_STALE_SECONDS + 1)
    ok, details = probe.check()
    assert not ok
    assert any("loop" in problem for problem in details["problems"])


def test_stale_telegram_tick_is_unhealthy():
    clock = FakeClock()
    probe = _alive(clock)
    clock.advance(TELEGRAM_STALE_SECONDS + 1)
    probe.tick("loop")  # the event loop is alive; only Telegram is silent
    ok, details = probe.check()
    assert not ok
    assert details["problems"] == [
        problem for problem in details["problems"] if "telegram" in problem
    ]


def test_missing_ticks_tolerated_only_on_startup():
    clock = FakeClock()
    probe = Health(clock=clock)
    assert probe.check()[0]  # warm-up: no heartbeat yet, which is fine
    clock.advance(LOOP_STALE_SECONDS + 1)
    assert not probe.check()[0]


async def test_finished_polling_is_unhealthy():
    async def stop() -> None:
        return None

    task = asyncio.create_task(stop())
    await task

    probe = _alive()
    probe.watch(polling=task)
    ok, details = probe.check()
    assert not ok
    assert any("polling" in problem for problem in details["problems"])


async def test_paused_broadcast_job_is_unhealthy():
    # regression: a paused broadcast job means the process lives but nothing sends
    sched = scheduler.start_scheduler(bot=None)
    try:
        probe = _alive()
        probe.watch(scheduler=sched)
        assert probe.check()[0]

        sched.pause_job(BROADCAST_JOB_ID)
        ok, details = probe.check()
        assert not ok
        assert any("scheduler" in problem for problem in details["problems"])
    finally:
        sched.shutdown(wait=False)


async def test_ping_telegram_ticks_only_on_success(monkeypatch):
    probe = Health(clock=FakeClock())
    monkeypatch.setattr(scheduler, "health", probe)

    class SilentBot:
        async def get_me(self):
            raise RuntimeError("no network")

    await scheduler._ping_telegram(SilentBot())
    assert "telegram" not in probe.check()[1]["last_tick"]

    class OkBot:
        async def get_me(self):
            return None

    await scheduler._ping_telegram(OkBot())
    assert "telegram" in probe.check()[1]["last_tick"]


async def test_healthz_returns_200_when_alive():
    async with TestClient(TestServer(build_app(_alive()))) as client:
        response = await client.get("/healthz")
        assert response.status == 200
        assert (await response.json())["status"] == "ok"


async def test_healthz_returns_503_when_stale():
    clock = FakeClock()
    probe = _alive(clock)
    clock.advance(LOOP_STALE_SECONDS + 1)

    async with TestClient(TestServer(build_app(probe))) as client:
        response = await client.get("/healthz")
        assert response.status == 503
        assert (await response.json())["status"] == "unhealthy"

from bot import db, scheduler


async def test_process_due_marks_sent(tmp_db):
    # with no subscribers broadcast_to_all never touches bot, so None is safe
    await db.init_db()
    await db.add_scheduled(
        text="hi",
        media_type=None,
        file_id=None,
        buttons=None,
        send_at="2000-01-01 00:00:00",
    )
    await scheduler._process_due(bot=None)
    assert await db.get_pending() == []


async def test_process_due_skips_future(tmp_db):
    await db.init_db()
    await db.add_scheduled(
        text="later",
        media_type=None,
        file_id=None,
        buttons=None,
        send_at="2099-01-01 00:00:00",
    )
    await scheduler._process_due(bot=None)
    assert len(await db.get_pending()) == 1


async def test_scheduler_job_is_not_paused():
    # regression: next_run_time=None paused the job, so broadcasts stopped going out
    sched = scheduler.start_scheduler(bot=None)
    try:
        job = sched.get_job("due_broadcasts")
        assert job is not None
        assert job.next_run_time is not None
    finally:
        sched.shutdown(wait=False)

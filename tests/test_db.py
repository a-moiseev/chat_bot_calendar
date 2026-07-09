from bot import db


async def _add(send_at="2099-01-01 19:00:00"):
    await db.add_scheduled(
        text="hi", media_type=None, file_id=None, buttons=None, send_at=send_at
    )


async def test_add_and_get_pending(tmp_db):
    await db.init_db()
    await _add()
    pending = await db.get_pending()
    assert len(pending) == 1
    assert pending[0].send_at == "2099-01-01 19:00:00"


async def test_delete_scheduled(tmp_db):
    await db.init_db()
    await _add()
    broadcast_id = (await db.get_pending())[0].id
    assert await db.delete_scheduled(broadcast_id) is True
    assert await db.get_pending() == []


async def test_delete_missing_returns_false(tmp_db):
    await db.init_db()
    assert await db.delete_scheduled(999) is False


async def test_delete_sent_returns_false(tmp_db):
    await db.init_db()
    await _add()
    broadcast_id = (await db.get_pending())[0].id
    await db.mark_sent(broadcast_id)
    assert await db.delete_scheduled(broadcast_id) is False


async def test_subscriber_upsert_updates_username(tmp_db):
    await db.init_db()
    await db.add_subscriber(1, "alice", "Alice")
    await db.add_subscriber(1, "alice_new", "Alice Cooper")
    subs = await db.get_all_subscribers()
    assert subs == [
        db.Subscriber(user_id=1, username="alice_new", full_name="Alice Cooper")
    ]


async def test_subscriber_upsert_keeps_name_when_not_given(tmp_db):
    await db.init_db()
    await db.add_subscriber(1, "alice", "Alice")
    await db.add_subscriber(1, None)
    subs = await db.get_all_subscribers()
    assert subs == [db.Subscriber(user_id=1, username=None, full_name="Alice")]


async def test_set_names(tmp_db):
    await db.init_db()
    await db.add_subscriber(1)
    await db.set_names(1, None, "Мария Иванова")
    subs = await db.get_all_subscribers()
    assert subs == [db.Subscriber(user_id=1, username=None, full_name="Мария Иванова")]

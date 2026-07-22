"""Tests for /start: subscribing the user and greeting them."""

from unittest.mock import AsyncMock

from bot import db
from bot.handlers import start


async def test_start_subscribes_and_greets(message, tmp_db, monkeypatch):
    await db.init_db()
    monkeypatch.setattr(start.config, "get_welcome_text", lambda: "Welcome!")
    message.chat.id = 77
    message.from_user = AsyncMock(username="jdoe", full_name="Jane Doe")

    await start.cmd_start(message)

    assert await db.get_all_subscribers() == [
        db.Subscriber(user_id=77, username="jdoe", full_name="Jane Doe")
    ]
    message.answer.assert_awaited_once_with("Welcome!")


async def test_start_without_a_from_user_still_subscribes(message, tmp_db, monkeypatch):
    """Channel posts carry no from_user; the chat id is all we can record."""
    await db.init_db()
    monkeypatch.setattr(start.config, "get_welcome_text", lambda: "Welcome!")
    message.chat.id = 88
    message.from_user = None

    await start.cmd_start(message)

    assert await db.get_all_subscribers() == [
        db.Subscriber(user_id=88, username=None, full_name=None)
    ]


async def test_start_twice_does_not_duplicate(message, tmp_db, monkeypatch):
    await db.init_db()
    monkeypatch.setattr(start.config, "get_welcome_text", lambda: "Welcome!")
    message.chat.id = 99
    message.from_user = AsyncMock(username="jdoe", full_name="Jane Doe")

    await start.cmd_start(message)
    await start.cmd_start(message)

    assert len(await db.get_all_subscribers()) == 1

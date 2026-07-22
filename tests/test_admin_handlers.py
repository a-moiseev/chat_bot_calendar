"""Tests for the admin commands: /help, /stats, /scheduled, /cancel_scheduled."""

from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramAPIError

from bot import db
from bot.handlers import admin


def _texts(mock: AsyncMock) -> list[str]:
    return [str(call.args[0]) for call in mock.answer.await_args_list]


async def test_help_answers_with_the_catalog_text(message):
    await admin.cmd_help(message)

    # the catalog help documents the wizard; enough to prove it came from there
    assert "/broadcast" in _texts(message)[0]


# --- /stats ---


async def test_stats_reports_when_there_are_no_subscribers(message, tmp_db):
    await db.init_db()

    await admin.cmd_stats(message, bot=AsyncMock())

    assert len(_texts(message)) == 1


async def test_stats_lists_subscribers_with_names(message, tmp_db):
    await db.init_db()
    await db.add_subscriber(1, "jdoe", "Jane Doe")
    await db.add_subscriber(2, None, "Мария Иванова")

    await admin.cmd_stats(message, bot=AsyncMock())

    sent = "\n".join(_texts(message))
    assert "Jane Doe @jdoe" in sent
    assert "Мария Иванова" in sent


async def test_stats_escapes_html_in_profile_names(message, tmp_db):
    """Names come from Telegram profiles, so they are attacker-controlled."""
    await db.init_db()
    await db.add_subscriber(1, None, "<b>x</b>")

    await admin.cmd_stats(message, bot=AsyncMock())

    sent = "\n".join(_texts(message))
    assert "&lt;b&gt;x&lt;/b&gt;" in sent
    assert "<b>x</b>" not in sent


async def test_stats_splits_long_lists_across_messages(message, tmp_db):
    await db.init_db()
    for i in range(1, 301):
        await db.add_subscriber(i, None, f"Subscriber number {i}")

    await admin.cmd_stats(message, bot=AsyncMock())

    sent = _texts(message)
    assert len(sent) > 1
    assert all(len(chunk) <= admin._CHUNK_LIMIT for chunk in sent)


async def test_stats_backfills_missing_names_via_get_chat(message, tmp_db):
    await db.init_db()
    await db.add_subscriber(1, None, None)
    bot = AsyncMock()
    bot.get_chat.return_value = AsyncMock(username="fetched", full_name="Fetched Name")

    await admin.cmd_stats(message, bot=bot)

    bot.get_chat.assert_awaited_once_with(1)
    # the fetched name is persisted, not just displayed
    assert (await db.get_all_subscribers())[0].full_name == "Fetched Name"


async def test_stats_survives_get_chat_failing(message, tmp_db):
    """A subscriber who blocked the bot must not break the whole listing."""
    await db.init_db()
    await db.add_subscriber(1, None, None)
    bot = AsyncMock()
    bot.get_chat.side_effect = TelegramAPIError(method=None, message="blocked")

    await admin.cmd_stats(message, bot=bot)

    assert _texts(message)


# --- /scheduled ---


async def test_scheduled_reports_when_empty(message, tmp_db):
    await db.init_db()

    await admin.cmd_scheduled(message)

    assert len(_texts(message)) == 1


async def test_scheduled_lists_pending_with_media_tag(message, tmp_db):
    await db.init_db()
    await db.add_scheduled(
        text="hello there",
        media_type="photo",
        file_id="f",
        buttons=None,
        send_at="2099-01-01 19:00:00",
    )

    await admin.cmd_scheduled(message)

    sent = "\n".join(_texts(message))
    assert "2099-01-01 19:00:00" in sent
    assert "photo" in sent
    assert "hello there" in sent


# --- /cancel_scheduled ---


@pytest.mark.parametrize("arg", ["", "   ", "abc", "3x"])
async def test_cancel_scheduled_rejects_a_non_numeric_id(message, arg):
    command = AsyncMock()
    command.args = arg

    await admin.cmd_cancel_scheduled(message, command)

    assert "/cancel_scheduled" in _texts(message)[0]


async def test_cancel_scheduled_removes_a_pending_broadcast(message, tmp_db):
    await db.init_db()
    await db.add_scheduled(
        text="x",
        media_type=None,
        file_id=None,
        buttons=None,
        send_at="2099-01-01 19:00:00",
    )
    pending_id = (await db.get_pending())[0].id
    command = AsyncMock()
    command.args = str(pending_id)

    await admin.cmd_cancel_scheduled(message, command)

    assert await db.get_pending() == []
    assert str(pending_id) in _texts(message)[0]


async def test_cancel_scheduled_reports_an_unknown_id(message, tmp_db):
    await db.init_db()
    command = AsyncMock()
    command.args = "999"

    await admin.cmd_cancel_scheduled(message, command)

    assert "999" in _texts(message)[0]

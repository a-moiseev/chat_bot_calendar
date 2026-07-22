"""Tests for the /broadcast FSM wizard.

The wizard is the most stateful part of the bot: each step both answers the
user and decides what the next state is. These tests drive the handlers
directly and assert on the state transition plus what reached Telegram.
"""

from unittest.mock import AsyncMock

import pytest
from aiogram.types import InaccessibleMessage

from bot import db
from bot.handlers import broadcast
from bot.states import BroadcastForm


@pytest.fixture(autouse=True)
def _no_real_sending(monkeypatch):
    """Stub the two functions that would talk to Telegram."""
    monkeypatch.setattr(broadcast, "send_to", AsyncMock())
    monkeypatch.setattr(broadcast, "broadcast_to_all", AsyncMock(return_value=(3, 1)))


def _texts(mock: AsyncMock) -> str:
    """Everything the handler sent, joined, for substring assertions."""
    return "\n".join(str(call.args[0]) for call in mock.answer.await_args_list)


# --- entering and leaving the wizard ---


async def test_cmd_broadcast_asks_for_text(message, state):
    await broadcast.cmd_broadcast(message, state)

    assert await state.get_state() == BroadcastForm.waiting_text
    message.answer.assert_awaited_once()


async def test_cmd_cancel_outside_the_wizard_stays_silent(message, state):
    await broadcast.cmd_cancel(message, state)

    message.answer.assert_not_awaited()


async def test_cmd_cancel_inside_the_wizard_clears_state(message, state):
    await state.set_state(BroadcastForm.waiting_text)

    await broadcast.cmd_cancel(message, state)

    assert await state.get_state() is None
    message.answer.assert_awaited_once()


# --- text -> media ---


async def test_got_text_stores_html_and_asks_for_media(message, state):
    message.html_text = "<b>bold</b> text"

    await broadcast.got_text(message, state)

    assert (await state.get_data())["text"] == "<b>bold</b> text"
    assert await state.get_state() == BroadcastForm.waiting_media


async def test_got_photo_keeps_the_largest_size(message, state):
    small, large = AsyncMock(), AsyncMock()
    small.file_id, large.file_id = "small", "large"
    message.photo = [small, large]

    await broadcast.got_photo(message, state)

    data = await state.get_data()
    assert (data["media_type"], data["file_id"]) == ("photo", "large")
    assert await state.get_state() == BroadcastForm.waiting_buttons


async def test_got_video_stores_file_id(message, state):
    message.video.file_id = "vid"

    await broadcast.got_video(message, state)

    data = await state.get_data()
    assert (data["media_type"], data["file_id"]) == ("video", "vid")


async def test_skip_media_clears_media_and_advances(callback, state):
    await broadcast.skip_media(callback, state)

    data = await state.get_data()
    assert data["media_type"] is None and data["file_id"] is None
    assert await state.get_state() == BroadcastForm.waiting_buttons
    callback.answer.assert_awaited_once()


# --- buttons ---


async def test_got_buttons_parses_and_shows_preview(message, state, tmp_db):
    await db.init_db()
    message.text = "Label - https://example.com"

    await broadcast.got_buttons(message, state)

    assert (await state.get_data())["buttons"] == [("Label", "https://example.com")]
    assert await state.get_state() == BroadcastForm.waiting_when


async def test_got_buttons_accepts_a_bare_link(message, state, tmp_db):
    await db.init_db()
    message.text = "https://example.com/x"

    await broadcast.got_buttons(message, state)

    assert (await state.get_data())["buttons"] == [
        ("example.com", "https://example.com/x")
    ]


async def test_got_buttons_explains_a_bad_line_and_keeps_the_state(message, state):
    await state.set_state(BroadcastForm.waiting_buttons)
    message.text = "Label - ftp://example.com"

    await broadcast.got_buttons(message, state)

    # the complaint quotes the offending URL, and the wizard does not advance
    assert "ftp://example.com" in _texts(message)
    assert await state.get_state() == BroadcastForm.waiting_buttons
    assert "buttons" not in await state.get_data()


async def test_skip_buttons_advances_with_no_buttons(callback, state, tmp_db):
    await db.init_db()

    await broadcast.skip_buttons(callback, state)

    assert (await state.get_data())["buttons"] == []
    assert await state.get_state() == BroadcastForm.waiting_when


# --- when to send ---


async def test_when_cancel_clears_state(callback, state):
    await state.set_state(BroadcastForm.waiting_when)

    await broadcast.when_cancel(callback, state)

    assert await state.get_state() is None
    callback.message.edit_text.assert_awaited_once()


async def test_when_now_broadcasts_and_reports_counts(callback, state):
    await state.update_data(text="hi", buttons=[])

    await broadcast.when_now(callback, state)

    broadcast.broadcast_to_all.assert_awaited_once()
    assert await state.get_state() is None
    # the stub reports (3, 1); both numbers must reach the admin
    reported = _texts(callback.message)
    assert "3" in reported and "1" in reported


async def test_when_schedule_asks_for_a_datetime(callback, state):
    await broadcast.when_schedule(callback, state)

    assert await state.get_state() == BroadcastForm.waiting_datetime


async def test_got_datetime_stores_the_broadcast(message, state, tmp_db):
    await db.init_db()
    await state.update_data(text="hi", media_type=None, file_id=None, buttons=[])
    message.text = "01.01.2099 19:00"

    await broadcast.got_datetime(message, state)

    pending = await db.get_pending()
    assert len(pending) == 1
    assert pending[0].send_at == "2099-01-01 19:00:00"
    assert await state.get_state() is None


async def test_got_datetime_rejects_an_unparseable_value(message, state, tmp_db):
    await db.init_db()
    await state.set_state(BroadcastForm.waiting_datetime)
    message.text = "sometime next week"

    await broadcast.got_datetime(message, state)

    assert await db.get_pending() == []
    assert await state.get_state() == BroadcastForm.waiting_datetime


async def test_got_datetime_rejects_a_past_moment(message, state, tmp_db):
    await db.init_db()
    await state.set_state(BroadcastForm.waiting_datetime)
    message.text = "01.01.2000 19:00"

    await broadcast.got_datetime(message, state)

    assert await db.get_pending() == []
    assert await state.get_state() == BroadcastForm.waiting_datetime


# --- the narrowing helpers ---


async def test_origin_rejects_an_inaccessible_message(callback):
    inaccessible = AsyncMock()
    inaccessible.__class__ = InaccessibleMessage
    callback.message = inaccessible

    with pytest.raises(RuntimeError, match="accessible"):
        broadcast._origin(callback)


async def test_bot_rejects_an_unbound_message(message):
    message.bot = None

    with pytest.raises(RuntimeError, match="Bot"):
        broadcast._bot(message)

from unittest.mock import AsyncMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message

from bot import db


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """An isolated temporary database for one test."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.sqlite3")


@pytest.fixture
def state() -> FSMContext:
    """A real FSMContext over in-memory storage.

    The wizard's whole job is moving between states, so faking the context
    would test the mock rather than the handler.
    """
    return FSMContext(
        storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=1, user_id=1)
    )


def _as(cls: type) -> AsyncMock:
    """An AsyncMock that passes isinstance() for `cls`.

    Assigning __class__ rather than passing spec=: aiogram types are pydantic
    models, so their fields (chat, photo, video) are not class attributes and a
    spec'd mock rejects them. Only the methods would survive, which is the
    wrong half.
    """
    mock = AsyncMock()
    mock.__class__ = cls
    return mock


@pytest.fixture
def message() -> AsyncMock:
    """A stand-in Message.

    isinstance() must succeed: bot.handlers.broadcast._origin uses it to narrow
    aiogram's Message | InaccessibleMessage | None.
    """
    msg = _as(Message)
    msg.chat.id = 1
    msg.text = ""
    msg.html_text = ""
    return msg


@pytest.fixture
def callback(message: AsyncMock) -> AsyncMock:
    """A stand-in CallbackQuery whose .message is the `message` fixture."""
    cb = _as(CallbackQuery)
    cb.message = message
    cb.data = ""
    return cb

"""Команда /start: подписка пользователя и приветствие."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot import config, db

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    username = message.from_user.username if message.from_user else None
    await db.add_subscriber(message.chat.id, username)
    await message.answer(config.get_welcome_text())

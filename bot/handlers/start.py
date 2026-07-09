"""Команда /start: подписка пользователя и приветствие."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot import config, db

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user = message.from_user
    username = user.username if user else None
    full_name = user.full_name if user else None
    await db.add_subscriber(message.chat.id, username, full_name)
    await message.answer(config.get_welcome_text())

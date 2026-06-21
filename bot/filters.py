"""Фильтры доступа."""

from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import Message

from bot.config import ADMIN_IDS


class IsAdmin(BaseFilter):
    """Пропускает только администраторов из ADMIN_IDS."""

    async def __call__(self, message: Message) -> bool:
        return message.from_user is not None and message.from_user.id in ADMIN_IDS

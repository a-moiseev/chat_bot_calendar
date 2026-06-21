"""Фильтры доступа."""

from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from bot.config import ADMIN_IDS


class IsAdmin(BaseFilter):
    """Пропускает только администраторов из ADMIN_IDS (сообщения и callback'и)."""

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        return event.from_user is not None and event.from_user.id in ADMIN_IDS

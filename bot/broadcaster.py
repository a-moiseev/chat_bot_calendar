"""Отправка одного сообщения и рассылка всем подписчикам."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from bot import db
from bot.keyboards import build_keyboard, load_buttons

logger = logging.getLogger(__name__)

# Лимит Telegram ~30 сообщений/сек; держим запас.
_RATE_LIMIT = 25
_DELAY = 1 / _RATE_LIMIT


@dataclass(slots=True)
class BroadcastPayload:
    text: str | None
    media_type: str | None  # 'photo' | 'video' | None
    file_id: str | None
    buttons: list[tuple[str, str]]

    @classmethod
    def from_scheduled(cls, row: db.ScheduledBroadcast) -> BroadcastPayload:
        return cls(
            text=row.text,
            media_type=row.media_type,
            file_id=row.file_id,
            buttons=load_buttons(row.buttons),
        )


def _messages_per_subscriber(payload: BroadcastPayload) -> int:
    """Сколько сообщений уходит одному подписчику — медиа и текст раздельно."""
    return (1 if payload.media_type else 0) + (1 if payload.text else 0) or 1


async def send_to(bot: Bot, chat_id: int, payload: BroadcastPayload) -> None:
    """Отправляет рассылку в конкретный чат.

    Медиа и текст шлём разными сообщениями: подпись к медиа Telegram
    ограничивает 1024 символами, а обычный текст — 4096. Кнопки вешаем на
    последнее сообщение (на текст, если он есть, иначе — на медиа).
    """
    markup = build_keyboard(payload.buttons)
    media_markup = None if payload.text else markup
    if payload.media_type == "photo":
        await bot.send_photo(chat_id, payload.file_id, reply_markup=media_markup)
    elif payload.media_type == "video":
        await bot.send_video(chat_id, payload.file_id, reply_markup=media_markup)
    if payload.text or not payload.media_type:
        await bot.send_message(chat_id, payload.text or "", reply_markup=markup)


async def broadcast_to_all(bot: Bot, payload: BroadcastPayload) -> tuple[int, int]:
    """Рассылает всем подписчикам. Возвращает (успешно, ошибок).

    Заблокировавших бота удаляет из БД, на flood-wait ждёт и повторяет.
    """
    sent = failed = 0
    # Медиа-рассылка шлёт по 2 сообщения на подписчика — троттлим по их числу,
    # чтобы суммарный темп остался в пределах лимита Telegram.
    delay = _DELAY * _messages_per_subscriber(payload)
    for chat_id in await db.get_all_subscriber_ids():
        try:
            await send_to(bot, chat_id, payload)
            sent += 1
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
            try:
                await send_to(bot, chat_id, payload)
                sent += 1
            except Exception:  # noqa: BLE001
                failed += 1
        except TelegramForbiddenError:
            await db.remove_subscriber(chat_id)
            failed += 1
        except Exception:  # noqa: BLE001
            logger.exception("Ошибка отправки в чат %s", chat_id)
            failed += 1
        await asyncio.sleep(delay)
    return sent, failed

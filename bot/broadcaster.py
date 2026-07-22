"""Sending a single message, and broadcasting to every subscriber."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from bot import db
from bot.keyboards import build_keyboard, load_buttons

logger = logging.getLogger(__name__)

# Telegram allows ~30 messages/sec; keep some headroom.
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
    """How many messages one subscriber receives: media and text go separately."""
    return (1 if payload.media_type else 0) + (1 if payload.text else 0) or 1


async def send_to(bot: Bot, chat_id: int, payload: BroadcastPayload) -> None:
    """Send the broadcast to one chat.

    Media and text go as separate messages: Telegram caps a media caption at
    1024 characters but allows 4096 for plain text. The keyboard is attached to
    the last message (the text if there is one, otherwise the media).
    """
    markup = build_keyboard(payload.buttons)
    media_markup = None if payload.text else markup
    if payload.media_type == "photo":
        await bot.send_photo(chat_id, payload.file_id or "", reply_markup=media_markup)
    elif payload.media_type == "video":
        await bot.send_video(chat_id, payload.file_id or "", reply_markup=media_markup)
    if payload.text or not payload.media_type:
        await bot.send_message(chat_id, payload.text or "", reply_markup=markup)


async def broadcast_to_all(bot: Bot, payload: BroadcastPayload) -> tuple[int, int]:
    """Broadcast to every subscriber. Returns (sent, failed).

    Subscribers who blocked the bot are dropped from the database; on a
    flood-wait we back off and retry once.
    """
    sent = failed = 0
    # A media broadcast sends 2 messages per subscriber, so throttle by that
    # count to keep the overall rate within Telegram's limit.
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
            logger.exception("Failed to send to chat %s", chat_id)
            failed += 1
        await asyncio.sleep(delay)
    return sent, failed

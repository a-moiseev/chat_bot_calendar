"""Admin commands: subscriber statistics and the list of broadcasts."""

from __future__ import annotations

import asyncio
import dataclasses
import html
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from bot import db
from bot.filters import IsAdmin
from bot.i18n import t

logger = logging.getLogger(__name__)

router = Router(name="admin")
router.message.filter(IsAdmin())

_CHUNK_LIMIT = 3500  # headroom under Telegram's 4096 limit

# Subscribers who joined before the full_name column existed are backfilled via
# getChat — one request per person, so process a bounded batch at a time.
_BACKFILL_LIMIT = 50
_BACKFILL_DELAY = 0.05


@router.message(F.text == "/help")
async def cmd_help(message: Message) -> None:
    await message.answer(t("help.text"))


async def _send_lines(message: Message, header: str, lines: list[str]) -> None:
    """Send a header plus lines, split into messages under the size limit."""
    chunk = header
    for line in lines:
        if len(chunk) + len(line) + 1 > _CHUNK_LIMIT:
            await message.answer(chunk)
            chunk = ""
        chunk = f"{chunk}\n{line}" if chunk else line
    if chunk:
        await message.answer(chunk)


async def _backfill_names(bot: Bot, subs: list[db.Subscriber]) -> list[db.Subscriber]:
    """Fetch names for subscribers missing one; returns the updated list."""
    missing = [s for s in subs if not s.full_name][:_BACKFILL_LIMIT]
    if not missing:
        return subs
    fetched: dict[int, db.Subscriber] = {}
    for sub in missing:
        try:
            chat = await bot.get_chat(sub.user_id)
        except TelegramAPIError as err:
            # Blocked the bot or deleted the account: leave the row as-is.
            logger.warning("getChat failed for %s: %s", sub.user_id, err)
            continue
        await db.set_names(sub.user_id, chat.username, chat.full_name)
        fetched[sub.user_id] = dataclasses.replace(
            sub, username=chat.username, full_name=chat.full_name
        )
        await asyncio.sleep(_BACKFILL_DELAY)
    return [fetched.get(s.user_id, s) for s in subs]


def _describe(sub: db.Subscriber) -> str:
    """Name and @username; the name comes from the profile, so escape it."""
    parts = []
    if sub.full_name:
        parts.append(html.escape(sub.full_name))
    if sub.username:
        parts.append(f"@{sub.username}")
    return " ".join(parts) or "—"


@router.message(F.text == "/stats")
async def cmd_stats(message: Message, bot: Bot) -> None:
    subs = await db.get_all_subscribers()
    if not subs:
        await message.answer(t("admin.no_subscribers"))
        return
    subs = await _backfill_names(bot, subs)
    header = t("admin.subscribers_header", count=len(subs))
    lines = [
        f"{i}. <code>{s.user_id}</code> {_describe(s)}" for i, s in enumerate(subs, 1)
    ]
    await _send_lines(message, header, lines)


@router.message(F.text == "/scheduled")
async def cmd_scheduled(message: Message) -> None:
    items = await db.get_pending()
    if not items:
        await message.answer(t("admin.no_scheduled"))
        return
    header = t("admin.scheduled_header", count=len(items))
    lines = []
    for it in items:
        snippet = html.escape((it.text or "").strip().replace("\n", " "))[:60]
        tags = []
        if it.media_type:
            tags.append(it.media_type)
        tag_str = f" [{', '.join(tags)}]" if tags else ""
        lines.append(
            t(
                "admin.scheduled_item",
                id=it.id,
                send_at=it.send_at,
                tags=tag_str,
                snippet=snippet,
            )
        )
    await _send_lines(message, header, lines)


@router.message(Command("cancel_scheduled"))
async def cmd_cancel_scheduled(message: Message, command: CommandObject) -> None:
    arg = (command.args or "").strip()
    if not arg.isdigit():
        await message.answer(t("admin.cancel_usage"))
        return
    if await db.delete_scheduled(int(arg)):
        await message.answer(t("admin.cancel_done", id=arg))
    else:
        await message.answer(t("admin.cancel_not_found", id=arg))

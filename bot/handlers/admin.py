"""Админские команды: статистика подписчиков и список рассылок."""

from __future__ import annotations

import asyncio
import dataclasses
import html
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from bot import config, db
from bot.filters import IsAdmin

logger = logging.getLogger(__name__)

router = Router(name="admin")
router.message.filter(IsAdmin())

_CHUNK_LIMIT = 3500  # запас под лимит Telegram 4096

# Подписчиков, подписавшихся до появления колонки full_name, дозаполняем через
# getChat — по одному запросу на человека, поэтому за раз берём ограниченную пачку.
_BACKFILL_LIMIT = 50
_BACKFILL_DELAY = 0.05


@router.message(F.text == "/help")
async def cmd_help(message: Message) -> None:
    await message.answer(config.get_help_text())


async def _send_lines(message: Message, header: str, lines: list[str]) -> None:
    """Отправляет заголовок и строки, разбивая на сообщения по лимиту."""
    chunk = header
    for line in lines:
        if len(chunk) + len(line) + 1 > _CHUNK_LIMIT:
            await message.answer(chunk)
            chunk = ""
        chunk = f"{chunk}\n{line}" if chunk else line
    if chunk:
        await message.answer(chunk)


async def _backfill_names(bot: Bot, subs: list[db.Subscriber]) -> list[db.Subscriber]:
    """Подтягивает имена тех, у кого они пустые, и возвращает обновлённый список."""
    missing = [s for s in subs if not s.full_name][:_BACKFILL_LIMIT]
    if not missing:
        return subs
    fetched: dict[int, db.Subscriber] = {}
    for sub in missing:
        try:
            chat = await bot.get_chat(sub.user_id)
        except TelegramAPIError as err:
            # Заблокировал бота или удалил аккаунт — оставляем как есть.
            logger.warning("getChat failed for %s: %s", sub.user_id, err)
            continue
        await db.set_names(sub.user_id, chat.username, chat.full_name)
        fetched[sub.user_id] = dataclasses.replace(
            sub, username=chat.username, full_name=chat.full_name
        )
        await asyncio.sleep(_BACKFILL_DELAY)
    return [fetched.get(s.user_id, s) for s in subs]


def _describe(sub: db.Subscriber) -> str:
    """Имя и @username; имя приходит из профиля, поэтому экранируем."""
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
        await message.answer("Подписчиков пока нет.")
        return
    subs = await _backfill_names(bot, subs)
    header = f"Подписчиков: <b>{len(subs)}</b>"
    lines = [
        f"{i}. <code>{s.user_id}</code> {_describe(s)}" for i, s in enumerate(subs, 1)
    ]
    await _send_lines(message, header, lines)


@router.message(F.text == "/scheduled")
async def cmd_scheduled(message: Message) -> None:
    items = await db.get_pending()
    if not items:
        await message.answer("Запланированных рассылок нет.")
        return
    header = (
        f"Запланировано: <b>{len(items)}</b>\n"
        "Отменить: <code>/cancel_scheduled id</code>"
    )
    lines = []
    for it in items:
        snippet = html.escape((it.text or "").strip().replace("\n", " "))[:60]
        tags = []
        if it.media_type:
            tags.append(it.media_type)
        tag_str = f" [{', '.join(tags)}]" if tags else ""
        lines.append(
            f"<b>#{it.id}</b> — {it.send_at} (мск){tag_str}\n{snippet}…"
        )
    await _send_lines(message, header, lines)


@router.message(Command("cancel_scheduled"))
async def cmd_cancel_scheduled(message: Message, command: CommandObject) -> None:
    arg = (command.args or "").strip()
    if not arg.isdigit():
        await message.answer("Укажите id рассылки: <code>/cancel_scheduled 3</code>")
        return
    if await db.delete_scheduled(int(arg)):
        await message.answer(f"Рассылка #{arg} отменена.")
    else:
        await message.answer(f"Рассылка #{arg} не найдена среди запланированных.")

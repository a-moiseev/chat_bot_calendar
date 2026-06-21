"""Админские команды: статистика подписчиков и список рассылок."""

from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.types import Message

from bot import db
from bot.filters import IsAdmin

router = Router(name="admin")
router.message.filter(IsAdmin)

_CHUNK_LIMIT = 3500  # запас под лимит Telegram 4096


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


@router.message(F.text == "/stats")
async def cmd_stats(message: Message) -> None:
    subs = await db.get_all_subscribers()
    if not subs:
        await message.answer("Подписчиков пока нет.")
        return
    header = f"Подписчиков: <b>{len(subs)}</b>"
    lines = [
        f"{i}. <code>{s.user_id}</code> "
        + (f"@{s.username}" if s.username else "—")
        for i, s in enumerate(subs, 1)
    ]
    await _send_lines(message, header, lines)


@router.message(F.text == "/scheduled")
async def cmd_scheduled(message: Message) -> None:
    items = await db.get_pending()
    if not items:
        await message.answer("Запланированных рассылок нет.")
        return
    header = f"Запланировано: <b>{len(items)}</b>"
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

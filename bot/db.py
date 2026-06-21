"""Хранилище: подписчики и отложенные рассылки (aiosqlite)."""

from __future__ import annotations

from dataclasses import dataclass

import aiosqlite

from bot.config import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS subscribers (
    user_id    INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS scheduled_broadcasts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    text       TEXT,
    media_type TEXT,
    file_id    TEXT,
    buttons    TEXT,
    send_at    TEXT NOT NULL,
    sent       INTEGER NOT NULL DEFAULT 0
);
"""


@dataclass(slots=True)
class ScheduledBroadcast:
    id: int
    text: str | None
    media_type: str | None
    file_id: str | None
    buttons: str | None
    send_at: str


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(_SCHEMA)
        await db.commit()


# --- subscribers ---


async def add_subscriber(user_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO subscribers (user_id) VALUES (?)", (user_id,)
        )
        await db.commit()


async def remove_subscriber(user_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM subscribers WHERE user_id = ?", (user_id,))
        await db.commit()


async def get_all_subscriber_ids() -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM subscribers") as cur:
            return [row[0] async for row in cur]


async def count_subscribers() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM subscribers") as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


# --- scheduled broadcasts ---


async def add_scheduled(
    *,
    text: str | None,
    media_type: str | None,
    file_id: str | None,
    buttons: str | None,
    send_at: str,
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO scheduled_broadcasts (text, media_type, file_id, buttons, send_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (text, media_type, file_id, buttons, send_at),
        )
        await db.commit()


async def get_due(now: str) -> list[ScheduledBroadcast]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, text, media_type, file_id, buttons, send_at "
            "FROM scheduled_broadcasts WHERE sent = 0 AND send_at <= ? ORDER BY send_at",
            (now,),
        ) as cur:
            return [ScheduledBroadcast(*row) async for row in cur]


async def mark_sent(broadcast_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE scheduled_broadcasts SET sent = 1 WHERE id = ?", (broadcast_id,)
        )
        await db.commit()

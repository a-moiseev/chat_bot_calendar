"""Хранилище: подписчики и отложенные рассылки (aiosqlite)."""

from __future__ import annotations

from dataclasses import dataclass

import aiosqlite

from bot.config import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS subscribers (
    user_id    INTEGER PRIMARY KEY,
    username   TEXT,
    full_name  TEXT,
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


@dataclass(slots=True)
class Subscriber:
    user_id: int
    username: str | None
    full_name: str | None


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(_SCHEMA)
        # миграция старых БД, где этих колонок ещё не было
        async with db.execute("PRAGMA table_info(subscribers)") as cur:
            columns = {row[1] async for row in cur}
        for column in ("username", "full_name"):
            if column not in columns:
                await db.execute(
                    f"ALTER TABLE subscribers ADD COLUMN {column} TEXT"  # noqa: S608
                )
        await db.commit()


# --- subscribers ---


async def add_subscriber(
    user_id: int, username: str | None = None, full_name: str | None = None
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO subscribers (user_id, username, full_name) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "  username = excluded.username, "
            # имя есть не у всех вызовов — не затираем уже сохранённое
            "  full_name = COALESCE(excluded.full_name, subscribers.full_name)",
            (user_id, username, full_name),
        )
        await db.commit()


async def set_names(user_id: int, username: str | None, full_name: str | None) -> None:
    """Обновляет имя и username подписчика (данные из getChat)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE subscribers SET username = ?, full_name = ? WHERE user_id = ?",
            (username, full_name, user_id),
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


async def get_all_subscribers() -> list[Subscriber]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id, username, full_name FROM subscribers ORDER BY created_at"
        ) as cur:
            return [Subscriber(*row) async for row in cur]


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


async def get_pending() -> list[ScheduledBroadcast]:
    """Ещё не отправленные отложенные рассылки, по возрастанию времени."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, text, media_type, file_id, buttons, send_at "
            "FROM scheduled_broadcasts WHERE sent = 0 ORDER BY send_at"
        ) as cur:
            return [ScheduledBroadcast(*row) async for row in cur]


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


async def delete_scheduled(broadcast_id: int) -> bool:
    """Удаляет ещё не отправленную рассылку. Возвращает True, если удалено."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "DELETE FROM scheduled_broadcasts WHERE id = ? AND sent = 0",
            (broadcast_id,),
        )
        await db.commit()
        return cur.rowcount > 0

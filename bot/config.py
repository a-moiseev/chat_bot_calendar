"""Конфигурация бота: токен, админы, текст приветствия."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("DB_PATH") or ROOT_DIR / "bot.sqlite3")
WELCOME_FILE = ROOT_DIR / "welcome.html"

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

ADMIN_IDS: set[int] = {
    int(part) for part in os.environ.get("ADMIN_IDS", "").replace(" ", "").split(",") if part
}


@lru_cache(maxsize=1)
def get_welcome_text() -> str:
    """Текст приветствия из welcome.html (читается один раз)."""
    if not WELCOME_FILE.exists():
        raise FileNotFoundError(
            f"Не найден {WELCOME_FILE.name}. Скопируйте welcome.example.html в "
            f"{WELCOME_FILE.name} и впишите текст приветствия."
        )
    return WELCOME_FILE.read_text(encoding="utf-8").strip()


def validate() -> None:
    """Проверка обязательных настроек при старте."""
    if not BOT_TOKEN:
        raise RuntimeError("Не задан BOT_TOKEN (см. .env.example).")
    if not ADMIN_IDS:
        raise RuntimeError("Не задан ADMIN_IDS (см. .env.example).")

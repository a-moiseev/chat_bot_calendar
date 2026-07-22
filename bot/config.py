"""Bot configuration: token, admins, and deployment-specific content."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("DB_PATH") or ROOT_DIR / "bot.sqlite3")
WELCOME_FILE = ROOT_DIR / "config" / "welcome.html"
HELP_FILE = ROOT_DIR / "config" / "help.html"

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

HEALTH_PORT = int(os.environ.get("HEALTH_PORT") or 8080)

ADMIN_IDS: set[int] = {
    int(part)
    for part in os.environ.get("ADMIN_IDS", "").replace(" ", "").split(",")
    if part
}


@lru_cache(maxsize=1)
def get_welcome_text() -> str:
    """Greeting text from welcome.html (read once per process)."""
    if not WELCOME_FILE.is_file():
        raise FileNotFoundError(
            "config/welcome.html not found. Copy config/welcome.example.html to "
            "config/welcome.html and write your greeting there."
        )
    return WELCOME_FILE.read_text(encoding="utf-8").strip()


@lru_cache(maxsize=1)
def get_help_text() -> str:
    """Текст справки для админов из help.html (читается один раз)."""
    if not HELP_FILE.is_file():
        raise FileNotFoundError("Не найден config/help.html.")
    return HELP_FILE.read_text(encoding="utf-8").strip()


def validate() -> None:
    """Validate required settings at startup."""
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set (see .env.example).")
    if not ADMIN_IDS:
        raise RuntimeError("ADMIN_IDS is not set (see .env.example).")

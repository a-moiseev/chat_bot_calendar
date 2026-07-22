"""Build the broadcast inline keyboard from 'Label - link' lines."""

from __future__ import annotations

import json

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def parse_buttons(text: str) -> list[tuple[str, str]]:
    """Parse lines of the form 'Label - https://...' into (label, url) pairs.

    The separator is ' - ', split on its last occurrence. Blank lines are
    skipped. Raises ButtonParseError if a line has no separator, has an empty
    part, or carries a non-http(s) URL.
    """
    buttons: list[tuple[str, str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if " - " not in line:
            raise ValueError(f"Строка без разделителя ' - ': {line!r}")
        # split on the last ' - ': a label may contain a dash, a URL may not
        label, url = line.rsplit(" - ", 1)
        label, url = label.strip(), url.strip()
        if not label or not url:
            raise ValueError(f"Пустой текст или ссылка: {line!r}")
        if not url.startswith(("http://", "https://")):
            raise ValueError(
                f"Ссылка должна начинаться с http:// или https://: {url!r}"
            )
        buttons.append((label, url))
    if not buttons:
        raise ValueError("Не найдено ни одной кнопки.")
    return buttons


def build_keyboard(buttons: list[tuple[str, str]]) -> InlineKeyboardMarkup | None:
    """One button per row."""
    if not buttons:
        return None
    rows = [[InlineKeyboardButton(text=label, url=url)] for label, url in buttons]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def dump_buttons(buttons: list[tuple[str, str]]) -> str:
    """Serialise buttons for storage in the database."""
    return json.dumps(buttons, ensure_ascii=False)


def load_buttons(data: str | None) -> list[tuple[str, str]]:
    """Deserialise buttons loaded from the database."""
    if not data:
        return []
    return [(label, url) for label, url in json.loads(data)]

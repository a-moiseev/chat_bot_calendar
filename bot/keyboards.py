"""Build the broadcast inline keyboard from 'Label - link' lines."""

from __future__ import annotations

import json

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


class ButtonParseError(ValueError):
    """A malformed button line.

    Carries a message key plus its parameters rather than a rendered string,
    so this module stays free of the locale layer and the caller decides which
    language to render the complaint in.
    """

    def __init__(self, key: str, **params: object) -> None:
        super().__init__(key)
        self.key = key
        self.params = params


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
            raise ButtonParseError("button_error.no_separator", line=line)
        # split on the last ' - ': a label may contain a dash, a URL may not
        label, url = line.rsplit(" - ", 1)
        label, url = label.strip(), url.strip()
        if not url.startswith(("http://", "https://")):
            raise ButtonParseError("button_error.bad_scheme", url=url)
        buttons.append((label, url))
    if not buttons:
        raise ButtonParseError("button_error.no_buttons")
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

"""Build the broadcast inline keyboard from 'Label - link' lines."""

from __future__ import annotations

import json
from urllib.parse import urlsplit

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


def _label_from_url(url: str) -> str:
    """Host of a bare URL, used as its button label: 'https://x.ru/a' -> 'x.ru'."""
    # rpartition, not partition: with no '@' present partition returns the host
    # in its *first* slot, so [-1] would be the empty string
    host = urlsplit(url).netloc.rpartition("@")[-1].partition(":")[0]
    return host.removeprefix("www.") or url


def parse_buttons(text: str) -> list[tuple[str, str]]:
    """Parse button lines into (label, url) pairs.

    A line is either 'Label - https://...' or a bare 'https://...', in which
    case the host becomes the label. The separator is ' - ', split on its last
    occurrence. Blank lines are skipped. Raises ButtonParseError if a line is
    neither form, has an empty part, or carries a non-http(s) URL.
    """
    buttons: list[tuple[str, str]] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        # Look for the separator in the unstripped line: stripping first would
        # eat the padding of a leading or trailing ' - ', hiding an empty part
        # behind a "no separator" complaint.
        if " - " in raw:
            # split on the last ' - ': a label may contain a dash, a URL may not
            label, url = raw.rsplit(" - ", 1)
            label, url = label.strip(), url.strip()
            if not label or not url:
                raise ButtonParseError("button_error.empty_part", line=raw.strip())
        else:
            url = raw.strip()
            if not url.startswith(("http://", "https://")):
                raise ButtonParseError("button_error.no_separator", line=url)
            label = _label_from_url(url)
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

"""Message catalog: user-facing strings from config/messages.<locale>.toml.

Only what a Telegram user or admin sees lives here. Operator-facing text —
startup errors, /healthz problems, log lines — stays hardcoded English in the
source, because its audience runs the bot rather than uses it.
"""

from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any

from bot import config

# Import the module, not `config.LOCALE` itself: `from ... import LOCALE` would
# bind the value at import time, so a test could never swap the locale.
MESSAGES_DIR = config.ROOT_DIR / "config"
DEFAULT_LOCALE = "en"


def _locale_file(locale: str) -> Path:
    return MESSAGES_DIR / f"messages.{locale}.toml"


def available_locales() -> list[str]:
    """Locales that ship a catalog, by filename."""
    return sorted(
        p.name.removeprefix("messages.").removesuffix(".toml")
        for p in MESSAGES_DIR.glob("messages.*.toml")
    )


def _flatten(section: dict[str, Any], prefix: str = "") -> dict[str, str]:
    """Nested TOML tables -> flat dotted keys ('broadcast.cancelled')."""
    flat: dict[str, str] = {}
    for key, value in section.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(_flatten(value, f"{path}."))
        else:
            # strip(): TOML keeps the newline before a closing ''' delimiter
            flat[path] = str(value).strip()
    return flat


@lru_cache(maxsize=None)
def load(locale: str) -> dict[str, str]:
    """Flat message map for a locale (read and parsed once per process)."""
    path = _locale_file(locale)
    if not path.is_file():
        raise FileNotFoundError(
            f"Locale file not found: {path}. "
            f"Set LOCALE to one of {available_locales()} (see .env.example)."
        )
    with path.open("rb") as fh:
        return _flatten(tomllib.load(fh))


def t(key: str, /, **params: object) -> str:
    """User-facing message by dotted key, with str.format() placeholders.

    Raises KeyError on an unknown key rather than falling back to another
    locale or echoing the key: a silent fallback would ship a half-translated
    UI that nobody notices. Both ways to hit it are closed at development time
    by tests/test_i18n.py — key parity across locales, and an AST sweep of
    every t() call site.
    """
    messages = load(config.LOCALE)
    try:
        template = messages[key]
    except KeyError:
        raise KeyError(
            f"Missing message key {key!r} in {_locale_file(config.LOCALE)}"
        ) from None
    return template.format(**params) if params else template


def validate() -> None:
    """Fail at startup if the selected locale is missing or malformed."""
    load(config.LOCALE)

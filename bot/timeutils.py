"""Time handling for scheduled broadcasts (Moscow time)."""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

MOSCOW_TZ = ZoneInfo("Europe/Moscow")
STORE_FMT = "%Y-%m-%d %H:%M:%S"

# Accepted input formats. Where the year is absent, the current one is used.
_DATETIME_FORMATS = (
    "%d.%m.%Y %H:%M",
    "%d.%m.%y %H:%M",
    "%d.%m %H:%M",
    "%Y-%m-%d %H:%M",
    "%d/%m/%Y %H:%M",
    "%d/%m/%y %H:%M",
    "%d/%m %H:%M",
)
_TIME_ONLY = re.compile(r"^(\d{1,2}):(\d{2})$")


def _now_naive() -> datetime:
    return datetime.now(MOSCOW_TZ).replace(tzinfo=None, microsecond=0)


def parse_send_at(text: str) -> str:
    """Parse a date/time (Moscow) into the stored 'YYYY-MM-DD HH:MM:SS' form.

    Accepts several formats: '24.06.2026 19:00', '24.06 19:00', '24/06/2026 19:00',
    '2026-06-24 19:00'. A missing year defaults to the current one; a bare time
    ('19:00') means today. Raises ValueError if nothing matches.
    """
    s = " ".join(text.strip().split())  # collapse repeated whitespace

    time_only = _TIME_ONLY.match(s)
    if time_only:
        hour, minute = int(time_only.group(1)), int(time_only.group(2))
        if hour > 23 or minute > 59:
            raise ValueError(f"Invalid time: {s!r}")
        dt = _now_naive().replace(hour=hour, minute=minute, second=0)
        return dt.strftime(STORE_FMT)

    year = _now_naive().year
    for fmt in _DATETIME_FORMATS:
        has_year = "%Y" in fmt or "%y" in fmt
        # prepend the current year for year-less formats, otherwise strptime
        # assumes 1900 and chokes on 29 February
        candidate = s if has_year else f"{year} {s}"
        candidate_fmt = fmt if has_year else f"%Y {fmt}"
        try:
            dt = datetime.strptime(candidate, candidate_fmt)
        except ValueError:
            continue
        return dt.strftime(STORE_FMT)

    raise ValueError(f"Could not parse date/time: {text!r}")


def now_str() -> str:
    """Current Moscow time in the stored format."""
    return _now_naive().strftime(STORE_FMT)


def is_future(send_at: str) -> bool:
    return send_at > now_str()

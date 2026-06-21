"""Работа со временем отложенных рассылок (московское время)."""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

MOSCOW_TZ = ZoneInfo("Europe/Moscow")
STORE_FMT = "%Y-%m-%d %H:%M:%S"

# Поддерживаемые форматы ввода. Где нет года — подставляется текущий.
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
    """Умный разбор даты/времени (мск) -> строка хранения 'ГГГГ-ММ-ДД ЧЧ:ММ:СС'.

    Понимает разные форматы: '24.06.2026 19:00', '24.06 19:00', '24/06/2026 19:00',
    '2026-06-24 19:00'. Если год не указан — текущий. Если указано только время
    ('19:00') — сегодняшняя дата. Бросает ValueError, если разобрать не удалось.
    """
    s = " ".join(text.strip().split())  # схлопываем лишние пробелы

    time_only = _TIME_ONLY.match(s)
    if time_only:
        hour, minute = int(time_only.group(1)), int(time_only.group(2))
        if hour > 23 or minute > 59:
            raise ValueError(f"Некорректное время: {s!r}")
        dt = _now_naive().replace(hour=hour, minute=minute, second=0)
        return dt.strftime(STORE_FMT)

    year = _now_naive().year
    for fmt in _DATETIME_FORMATS:
        has_year = "%Y" in fmt or "%y" in fmt
        # для форматов без года подставляем текущий перед разбором
        # (иначе strptime берёт 1900 и ломается на 29 февраля)
        candidate = s if has_year else f"{year} {s}"
        candidate_fmt = fmt if has_year else f"%Y {fmt}"
        try:
            dt = datetime.strptime(candidate, candidate_fmt)
        except ValueError:
            continue
        return dt.strftime(STORE_FMT)

    raise ValueError(f"Не удалось разобрать дату/время: {text!r}")


def now_str() -> str:
    """Текущее московское время в формате хранения."""
    return _now_naive().strftime(STORE_FMT)


def is_future(send_at: str) -> bool:
    return send_at > now_str()

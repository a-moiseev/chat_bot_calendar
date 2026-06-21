"""Работа со временем отложенных рассылок (московское время)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

MOSCOW_TZ = ZoneInfo("Europe/Moscow")
INPUT_FMT = "%d.%m.%Y %H:%M"
STORE_FMT = "%Y-%m-%d %H:%M:%S"


def parse_send_at(text: str) -> str:
    """'ДД.ММ.ГГГГ ЧЧ:ММ' (мск) -> строка хранения 'ГГГГ-ММ-ДД ЧЧ:ММ:СС'.

    Бросает ValueError при неверном формате.
    """
    dt = datetime.strptime(text.strip(), INPUT_FMT)
    return dt.strftime(STORE_FMT)


def now_str() -> str:
    """Текущее московское время в формате хранения."""
    return datetime.now(MOSCOW_TZ).strftime(STORE_FMT)


def is_future(send_at: str) -> bool:
    return send_at > now_str()

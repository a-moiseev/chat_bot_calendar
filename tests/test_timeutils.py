import pytest

from bot.timeutils import _now_naive, is_future, parse_send_at


def test_parse_full_format():
    assert parse_send_at("24.06.2026 19:00") == "2026-06-24 19:00:00"


def test_parse_strips_and_collapses_whitespace():
    assert parse_send_at("  01.01.2030   09:05 ") == "2030-01-01 09:05:00"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("24.06.2026 19:00", "2026-06-24 19:00:00"),
        ("24.06.26 19:00", "2026-06-24 19:00:00"),
        ("2026-06-24 19:00", "2026-06-24 19:00:00"),
        ("24/06/2026 19:00", "2026-06-24 19:00:00"),
    ],
)
def test_parse_various_formats(text, expected):
    assert parse_send_at(text) == expected


def test_parse_without_year_uses_current():
    year = _now_naive().year
    assert parse_send_at("24.06 19:00") == f"{year}-06-24 19:00:00"


def test_parse_time_only_uses_today():
    today = _now_naive().date().isoformat()
    assert parse_send_at("19:00") == f"{today} 19:00:00"
    assert parse_send_at("9:05") == f"{today} 09:05:00"


@pytest.mark.parametrize(
    "text",
    ["24.06.2026", "bad", "32.13.2026 19:00", "25:00", "19:99", ""],
)
def test_parse_invalid_raises(text):
    with pytest.raises(ValueError):
        parse_send_at(text)


def test_is_future():
    assert is_future("2099-01-01 00:00:00") is True
    assert is_future("2000-01-01 00:00:00") is False

import pytest

from bot.timeutils import is_future, parse_send_at


def test_parse_valid():
    assert parse_send_at("24.06.2026 19:00") == "2026-06-24 19:00:00"


def test_parse_strips_whitespace():
    assert parse_send_at("  01.01.2030 09:05 ") == "2030-01-01 09:05:00"


@pytest.mark.parametrize(
    "text",
    ["2026-06-24 19:00", "24/06/2026 19:00", "24.06.2026", "bad", "32.13.2026 99:99"],
)
def test_parse_invalid_raises(text):
    with pytest.raises(ValueError):
        parse_send_at(text)


def test_is_future():
    assert is_future("2099-01-01 00:00:00") is True
    assert is_future("2000-01-01 00:00:00") is False

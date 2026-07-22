import pytest

from bot.keyboards import (
    ButtonParseError,
    build_keyboard,
    dump_buttons,
    load_buttons,
    parse_buttons,
)


def test_parse_single_button():
    assert parse_buttons("Pick a course - https://example.com") == [
        ("Pick a course", "https://example.com")
    ]


def test_parse_multiple_and_skip_blank_lines():
    text = "A - https://a.com\n\n  B - http://b.com  \n"
    assert parse_buttons(text) == [("A", "https://a.com"), ("B", "http://b.com")]


def test_parse_label_with_inner_dash():
    # split on the last ' - ', so a dash inside the label survives
    assert parse_buttons("Course - discount - https://x.com") == [
        ("Course - discount", "https://x.com")
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("https://example.com", [("example.com", "https://example.com")]),
        # www. is noise on a button label
        (
            "https://www.example.com/a/b",
            [("example.com", "https://www.example.com/a/b")],
        ),
        (
            "http://sub.example.co.uk:8080/x",
            [("sub.example.co.uk", "http://sub.example.co.uk:8080/x")],
        ),
        # mixed with the labelled form, and indented
        (
            "  https://a.com\nLabel - https://b.com",
            [("a.com", "https://a.com"), ("Label", "https://b.com")],
        ),
    ],
)
def test_parse_bare_link_uses_host_as_label(text, expected):
    assert parse_buttons(text) == expected


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ("no separator here", "button_error.no_separator"),
        ("example.com", "button_error.no_separator"),  # bare, but not http(s)
        ("Label - ftp://x.com", "button_error.bad_scheme"),
        # the separator is matched before stripping, so its padding survives
        # and these report the empty part rather than a missing separator
        (" - https://x.com", "button_error.empty_part"),
        ("Label - ", "button_error.empty_part"),
        ("", "button_error.no_buttons"),
    ],
)
def test_parse_invalid_raises(text, key):
    with pytest.raises(ButtonParseError) as excinfo:
        parse_buttons(text)
    assert excinfo.value.key == key


def test_button_parse_error_is_a_value_error():
    """Callers that only catch ValueError keep working."""
    with pytest.raises(ValueError):
        parse_buttons("no separator here")


def test_build_keyboard_one_row_per_button():
    kb = build_keyboard([("A", "https://a.com"), ("B", "https://b.com")])
    assert kb is not None
    assert len(kb.inline_keyboard) == 2
    assert kb.inline_keyboard[0][0].url == "https://a.com"


def test_build_keyboard_empty_is_none():
    assert build_keyboard([]) is None


def test_dump_load_roundtrip():
    # non-ASCII round-trips intact (dump uses ensure_ascii=False)
    buttons = [("Привет", "https://example.com/п")]
    assert load_buttons(dump_buttons(buttons)) == buttons


def test_load_empty():
    assert load_buttons(None) == []
    assert load_buttons("") == []

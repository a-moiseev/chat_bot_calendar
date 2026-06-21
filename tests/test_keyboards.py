import pytest

from bot.keyboards import build_keyboard, dump_buttons, load_buttons, parse_buttons


def test_parse_single_button():
    assert parse_buttons("Выбрать курс - https://example.com") == [
        ("Выбрать курс", "https://example.com")
    ]


def test_parse_multiple_and_skip_blank_lines():
    text = "A - https://a.com\n\n  B - http://b.com  \n"
    assert parse_buttons(text) == [("A", "https://a.com"), ("B", "http://b.com")]


def test_parse_label_with_inner_dash():
    # разделитель — первое ' - ', тире внутри текста сохраняется
    assert parse_buttons("Курс - скидка - https://x.com") == [
        ("Курс - скидка", "https://x.com")
    ]


@pytest.mark.parametrize(
    "text",
    ["нет разделителя", "Текст - ftp://x.com", " - https://x.com", "Текст - ", ""],
)
def test_parse_invalid_raises(text):
    with pytest.raises(ValueError):
        parse_buttons(text)


def test_build_keyboard_one_row_per_button():
    kb = build_keyboard([("A", "https://a.com"), ("B", "https://b.com")])
    assert kb is not None
    assert len(kb.inline_keyboard) == 2
    assert kb.inline_keyboard[0][0].url == "https://a.com"


def test_build_keyboard_empty_is_none():
    assert build_keyboard([]) is None


def test_dump_load_roundtrip():
    buttons = [("Привет", "https://example.com/п")]
    assert load_buttons(dump_buttons(buttons)) == buttons


def test_load_empty():
    assert load_buttons(None) == []
    assert load_buttons("") == []

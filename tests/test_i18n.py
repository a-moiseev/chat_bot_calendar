"""Tests for the message catalog.

The first three are load-bearing: bot.i18n.t() raises on an unknown key
instead of falling back to another locale, and these are what make that safe.
They close both ways to hit it — a translator omitting a key, and a developer
typo'ing one at a call site.
"""

import ast
import pathlib
import re
import string

import pytest

from bot import config, i18n

LOCALES = i18n.available_locales()
BOT_DIR = pathlib.Path(i18n.__file__).parent

# Commands the bot registers that the admin help is expected to document.
ADMIN_COMMANDS = [
    "/broadcast",
    "/cancel",
    "/stats",
    "/scheduled",
    "/cancel_scheduled",
    "/help",
]


def _placeholders(template: str) -> set[str]:
    return {
        field
        for _, field, _, _ in string.Formatter().parse(template)
        if field is not None
    }


def _call_site_keys() -> set[str]:
    """Every literal key passed to t() anywhere under bot/."""
    keys: set[str] = set()
    for path in BOT_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "t"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                keys.add(node.args[0].value)
    return keys


def test_locales_are_discovered():
    assert i18n.DEFAULT_LOCALE in LOCALES
    assert "ru" in LOCALES


@pytest.mark.parametrize("locale", LOCALES)
def test_all_locales_have_same_keys(locale):
    reference = set(i18n.load(i18n.DEFAULT_LOCALE))
    keys = set(i18n.load(locale))
    assert keys == reference, (
        f"{locale} differs from {i18n.DEFAULT_LOCALE}: "
        f"missing={sorted(reference - keys)} extra={sorted(keys - reference)}"
    )


@pytest.mark.parametrize("locale", LOCALES)
def test_all_locales_have_same_placeholders(locale):
    """A renamed placeholder would raise KeyError only under that locale."""
    reference = i18n.load(i18n.DEFAULT_LOCALE)
    for key, template in i18n.load(locale).items():
        assert _placeholders(template) == _placeholders(reference[key]), (
            f"{locale}:{key} placeholders differ from {i18n.DEFAULT_LOCALE}"
        )


def test_every_call_site_key_exists():
    """Catches a typo'd key at a t() call site before it reaches a user."""
    catalog = i18n.load(i18n.DEFAULT_LOCALE)
    unknown = sorted(key for key in _call_site_keys() if key not in catalog)
    assert not unknown, f"t() called with keys absent from the catalog: {unknown}"


@pytest.mark.parametrize("locale", LOCALES)
def test_skip_word_matches_button_label(locale):
    """Prose naming the skip button must match the button's own label."""
    messages = i18n.load(locale)
    assert messages["word.skip"] in messages["button.skip"]


@pytest.mark.parametrize("locale", LOCALES)
def test_help_documents_every_admin_command(locale):
    text = i18n.load(locale)["help.text"]
    for command in ADMIN_COMMANDS:
        assert command in text, f"{locale} help omits {command}"


@pytest.mark.parametrize("locale", LOCALES)
def test_html_tags_are_balanced(locale):
    """An unbalanced tag makes Telegram reject the send with a 400.

    parse_mode=HTML is global, so a translator's stray <b> is a silent
    production failure rather than a cosmetic bug.
    """
    for key, template in i18n.load(locale).items():
        stack: list[str] = []
        for closing, name in re.findall(r"<(/?)([a-z]+)[^>]*>", template):
            if closing:
                assert stack and stack[-1] == name, (
                    f"{locale}:{key} closes <{name}> out of order"
                )
                stack.pop()
            else:
                stack.append(name)
        assert not stack, f"{locale}:{key} leaves {stack} unclosed"


def test_missing_key_raises():
    with pytest.raises(KeyError):
        i18n.t("nope.not_a_key")


def test_unknown_locale_fails_loud(monkeypatch):
    monkeypatch.setattr(config, "LOCALE", "xx")
    with pytest.raises(FileNotFoundError) as excinfo:
        i18n.validate()
    assert "xx" in str(excinfo.value)
    assert i18n.DEFAULT_LOCALE in str(excinfo.value)


def test_format_conversion_preserved():
    """!r survived the move from f-strings to TOML templates."""
    rendered = i18n.t("button_error.no_separator", line="a - b")
    assert "'a - b'" in rendered

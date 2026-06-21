"""Построение инлайн-клавиатуры рассылки из строк 'Текст - ссылка'."""

from __future__ import annotations

import json

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def parse_buttons(text: str) -> list[tuple[str, str]]:
    """Разбирает строки вида 'Текст - https://...' в пары (текст, url).

    Разделитель — ' - ' (первое вхождение). Пустые строки пропускаются.
    Бросает ValueError, если в строке нет разделителя или url не http(s).
    """
    buttons: list[tuple[str, str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if " - " not in line:
            raise ValueError(f"Строка без разделителя ' - ': {line!r}")
        # делим по последнему ' - ': в тексте кнопки может быть тире, в URL — нет
        label, url = line.rsplit(" - ", 1)
        label, url = label.strip(), url.strip()
        if not label or not url:
            raise ValueError(f"Пустой текст или ссылка: {line!r}")
        if not url.startswith(("http://", "https://")):
            raise ValueError(f"Ссылка должна начинаться с http:// или https://: {url!r}")
        buttons.append((label, url))
    if not buttons:
        raise ValueError("Не найдено ни одной кнопки.")
    return buttons


def build_keyboard(buttons: list[tuple[str, str]]) -> InlineKeyboardMarkup | None:
    """Каждая кнопка — отдельным рядом."""
    if not buttons:
        return None
    rows = [[InlineKeyboardButton(text=label, url=url)] for label, url in buttons]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def dump_buttons(buttons: list[tuple[str, str]]) -> str:
    """Сериализация кнопок для хранения в БД."""
    return json.dumps(buttons, ensure_ascii=False)


def load_buttons(data: str | None) -> list[tuple[str, str]]:
    """Десериализация кнопок из БД."""
    if not data:
        return []
    return [(label, url) for label, url in json.loads(data)]

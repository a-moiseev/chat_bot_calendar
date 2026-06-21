# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Что это

Telegram-бот рассылки на **aiogram 3.x** (Python 3.13). Пользователь жмёт `/start` → подписывается; админ командой `/broadcast` собирает сообщение и шлёт его всем подписчикам — сразу или по расписанию.

## Окружение и команды

Пакетный менеджер — **uv** (`uv pip` + `requirements.txt`, без `pyproject.toml`).

```bash
uv venv --python 3.13
uv pip install -r requirements.txt

cp .env.example .env                       # вписать BOT_TOKEN и ADMIN_IDS
cp welcome.example.html welcome.html       # текст приветствия

.venv/bin/python -m bot.main               # запуск бота
.venv/bin/python -m pytest                 # тесты
.venv/bin/ruff check . && .venv/bin/ruff format .
.venv/bin/mypy .
```

После добавления зависимости пинить её версию в `requirements.txt` (`uv pip show <pkg>`).

## Архитектура

Точка входа `bot/main.py` поднимает `Bot`/`Dispatcher` (глобальный `parse_mode=HTML`), инициализирует БД, регистрирует роутеры и стартует планировщик.

- `bot/config.py` — `BOT_TOKEN`, `ADMIN_IDS` из `.env`; `get_welcome_text()` лениво читает `welcome.html` (кэш). `welcome.html` в `.gitignore`, шаблон — `welcome.example.html`.
- `bot/db.py` — aiosqlite, файл `bot.sqlite3` (игнорируется). Таблицы `subscribers` и `scheduled_broadcasts`.
- `bot/handlers/start.py` — `/start`: `add_subscriber` + приветствие.
- `bot/handlers/broadcast.py` — FSM-мастер (`bot/states.py`): текст → медиа → кнопки → когда (сейчас/по расписанию) → отправка. Только для админов (`bot/filters.py: IsAdmin`).
- `bot/keyboards.py` — `parse_buttons` (строки `Текст - ссылка`, делит по **последнему** ` - `), `build_keyboard`, сериализация кнопок в JSON для БД.
- `bot/broadcaster.py` — `BroadcastPayload` + `send_to`/`broadcast_to_all` (троттлинг ~25 msg/s, удаление заблокировавших, обработка flood-wait). Единый путь отправки для немедленных и отложенных рассылок.
- `bot/scheduler.py` — APScheduler опрашивает `get_due` раз в минуту и шлёт созревшие рассылки (переживает рестарты, без job-store).
- `bot/timeutils.py` — парсинг `ДД.ММ.ГГГГ ЧЧ:ММ` (мск) и сравнение с `now`.

## Важные детали

- Текст рассылки берётся как `message.html_text`, чтобы сохранить нативное форматирование Telegram (жирный/курсив/ссылки).
- Время отложенных рассылок — **московское** (`Europe/Moscow`); хранится строкой `ГГГГ-ММ-ДД ЧЧ:ММ:СС`, сравнение строковое (формат фиксированной ширины).
- Приветствие после `/start` шлёт только код — BotFather умеет лишь Description до нажатия Start.

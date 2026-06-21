# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Что это

Telegram-бот рассылки на **aiogram 3.x** (Python 3.13). Пользователь жмёт `/start` → подписывается; админ командой `/broadcast` собирает сообщение и шлёт его всем подписчикам — сразу или по расписанию.

## Окружение и команды

Пакетный менеджер — **uv** (`uv pip` + `requirements.txt`, без `pyproject.toml`).

```bash
uv venv --python 3.13
uv pip install -r requirements.txt

cp .env.example .env                                 # вписать BOT_TOKEN и ADMIN_IDS
cp config/welcome.example.html config/welcome.html   # текст приветствия

.venv/bin/python -m bot.main               # запуск бота
.venv/bin/python -m pytest                 # тесты
.venv/bin/ruff check . && .venv/bin/ruff format .
.venv/bin/mypy .
```

После добавления зависимости пинить её версию в `requirements.txt` (`uv pip show <pkg>`).

## Архитектура

Точка входа `bot/main.py` поднимает `Bot`/`Dispatcher` (глобальный `parse_mode=HTML`), инициализирует БД, регистрирует роутеры и стартует планировщик.

- `bot/config.py` — `BOT_TOKEN`, `ADMIN_IDS` из `.env`; `get_welcome_text()` лениво читает `config/welcome.html` (кэш). `config/welcome.html` в `.gitignore`, шаблон — `config/welcome.example.html`. В Docker монтируется каталог `./config` (каталог, а не файл — иначе bind-mount создаёт пустую папку).
- `bot/db.py` — aiosqlite, файл `bot.sqlite3` (игнорируется). Таблицы `subscribers` и `scheduled_broadcasts`.
- `bot/handlers/start.py` — `/start`: `add_subscriber` (с username) + приветствие.
- `bot/handlers/broadcast.py` — FSM-мастер (`bot/states.py`): текст → медиа → кнопки → когда (сейчас/по расписанию) → отправка. Только для админов (`bot/filters.py: IsAdmin`).
- `bot/handlers/admin.py` — админские `/stats` (число и список подписчиков), `/scheduled` (список отложенных) и `/cancel_scheduled <id>` (отмена отложенной); длинные ответы режутся на части по лимиту Telegram.
- `bot/keyboards.py` — `parse_buttons` (строки `Текст - ссылка`, делит по **последнему** ` - `), `build_keyboard`, сериализация кнопок в JSON для БД.
- `bot/broadcaster.py` — `BroadcastPayload` + `send_to`/`broadcast_to_all` (троттлинг ~25 msg/s, удаление заблокировавших, обработка flood-wait). Единый путь отправки для немедленных и отложенных рассылок.
- `bot/scheduler.py` — APScheduler опрашивает `get_due` раз в минуту и шлёт созревшие рассылки (переживает рестарты, без job-store).
- `bot/timeutils.py` — умный парсинг даты/времени (мск): разные форматы, год по умолчанию текущий, только время = сегодня; сравнение с `now`.

## Деплой

Пуш в `master` → `.github/workflows/deploy.yml`: тесты, затем SSH на VPS (`appleboy/ssh-action`), `git pull` в `/opt/chat_bot_calendar` и `docker compose up -d --build`. Образ — `Dockerfile` (база `ghcr.io/astral-sh/uv`, `uv pip install --system`). `docker-compose.yml` пробрасывает `BOT_TOKEN`/`ADMIN_IDS` из окружения и монтирует `./config` (ro, там `welcome.html`) и `./data` (там SQLite, `DB_PATH=/app/data/bot.sqlite3`). GitHub: секреты `VPS_HOST/VPS_USER/VPS_SSH_KEY/BOT_TOKEN`, переменная `ADMIN_IDS`.

## Важные детали

- Текст рассылки берётся как `message.html_text`, чтобы сохранить нативное форматирование Telegram (жирный/курсив/ссылки).
- Время отложенных рассылок — **московское** (`Europe/Moscow`); хранится строкой `ГГГГ-ММ-ДД ЧЧ:ММ:СС`, сравнение строковое (формат фиксированной ширины).
- Приветствие после `/start` шлёт только код — BotFather умеет лишь Description до нажатия Start.

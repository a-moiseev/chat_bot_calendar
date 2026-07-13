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

- `bot/config.py` — `BOT_TOKEN`, `ADMIN_IDS` из `.env`; `get_welcome_text()` лениво читает `config/welcome.html` (кэш). `config/welcome.html` в `.gitignore`, шаблон — `config/welcome.example.html`. `get_help_text()` так же читает `config/help.html` (этот файл закоммичен — справка по командам). В Docker монтируется каталог `./config` (каталог, а не файл — иначе bind-mount создаёт пустую папку).
- `bot/db.py` — aiosqlite, файл `bot.sqlite3` (игнорируется). Таблицы `subscribers` (`user_id`, `username`, `full_name`) и `scheduled_broadcasts`. `init_db` доливает недостающие колонки в старые БД через `PRAGMA table_info`.
- `bot/handlers/start.py` — `/start`: `add_subscriber` (с username и именем) + приветствие.
- `bot/handlers/broadcast.py` — FSM-мастер (`bot/states.py`): текст → медиа → кнопки → когда (сейчас/по расписанию) → отправка. Только для админов (`bot/filters.py: IsAdmin`).
- `bot/handlers/admin.py` — админские `/help` (текст из `config/help.html`), `/stats` (число и список подписчиков), `/scheduled` (список отложенных) и `/cancel_scheduled <id>` (отмена отложенной); длинные ответы режутся на части по лимиту Telegram. `/stats` перед выводом дозаполняет пустые `full_name` через `getChat` (пачками по 50) — так подтягиваются имена тех, кто подписался до появления колонки. Имя приходит из профиля, поэтому в вывод идёт только через `html.escape` (`parse_mode=HTML` глобальный).
- `bot/keyboards.py` — `parse_buttons` (строки `Текст - ссылка`, делит по **последнему** ` - `), `build_keyboard`, сериализация кнопок в JSON для БД.
- `bot/broadcaster.py` — `BroadcastPayload` + `send_to`/`broadcast_to_all` (троттлинг ~25 msg/s, удаление заблокировавших, обработка flood-wait). Единый путь отправки для немедленных и отложенных рассылок.
- `bot/scheduler.py` — APScheduler опрашивает `get_due` раз в минуту и шлёт созревшие рассылки (переживает рестарты, без job-store). Плюс два служебных job'а для probe: `heartbeat` (раз в 30 с) и `telegram_ping` (`getMe` раз в 5 минут).
- `bot/health.py` — liveness probe: aiohttp-сервер на `HEALTH_PORT` (8080), `GET /healthz` → 200 или 503 со списком `problems`. Нездоров, если умер polling-таск, протух пульс `loop` (>180 с) или `telegram` (>15 мин), либо задача `due_broadcasts` на паузе. Пульс `loop` — отдельный job, а не тик внутри `_process_due`: у того `max_instances=1`, и длинная рассылка (25 msg/s) съела бы слот, дав ложный алярм. Пороги на старте прощаются, пока `uptime` меньше лимита, — иначе деплой падал бы в первую минуту.
- `bot/timeutils.py` — умный парсинг даты/времени (мск): разные форматы, год по умолчанию текущий, только время = сегодня; сравнение с `now`.

## Деплой

Пуш в `master` → `.github/workflows/deploy.yml`: тесты, затем SSH на VPS (`appleboy/ssh-action`), `git pull` в `/opt/chat_bot_calendar` и `docker compose up -d --build`; деплой ждёт 200 от `/healthz` до 60 с и падает, если не дождался. Образ — `Dockerfile` (база `ghcr.io/astral-sh/uv`, `uv pip install --system`). `docker-compose.yml` пробрасывает `BOT_TOKEN`/`ADMIN_IDS` из окружения и монтирует `./config` (ro, там `welcome.html`) и `./data` (там SQLite, `DB_PATH=/app/data/bot.sqlite3`). GitHub: секреты `VPS_HOST/VPS_USER/VPS_SSH_KEY/BOT_TOKEN`, переменная `ADMIN_IDS`.

## Важные детали

- Текст рассылки берётся как `message.html_text`, чтобы сохранить нативное форматирование Telegram (жирный/курсив/ссылки).
- Время отложенных рассылок — **московское** (`Europe/Moscow`); хранится строкой `ГГГГ-ММ-ДД ЧЧ:ММ:СС`, сравнение строковое (формат фиксированной ширины).
- Приветствие после `/start` шлёт только код — BotFather умеет лишь Description до нажатия Start.

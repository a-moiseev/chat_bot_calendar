# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Telegram broadcast bot on **aiogram 3.x** (Python 3.13). A user presses `/start` and is
subscribed; an admin composes a message with `/broadcast` and sends it to every subscriber,
either immediately or on a schedule.

## Environment and commands

The package manager is **uv** (`uv pip` + `requirements.txt`, no `pyproject.toml`).

```bash
uv venv --python 3.13
uv pip install -r requirements.txt

cp .env.example .env                                 # fill in BOT_TOKEN and ADMIN_IDS
cp config/welcome.example.html config/welcome.html   # the greeting text

.venv/bin/python -m bot.main               # run the bot
.venv/bin/python -m pytest                 # tests
.venv/bin/ruff check . && .venv/bin/ruff format .
.venv/bin/mypy .
```

Pin any new dependency in `requirements.txt` (`uv pip show <pkg>`).

## Architecture

`bot/main.py` builds `Bot`/`Dispatcher` (global `parse_mode=HTML`), initialises the
database, registers routers and starts the scheduler.

- `bot/config.py` — `BOT_TOKEN`, `ADMIN_IDS`, `LOCALE` from `.env`. `get_welcome_text()`
  lazily reads `config/welcome.html` (cached). That file is gitignored; the template is
  `config/welcome.example.html`. Docker mounts the `./config` **directory** (not the
  single file — a bind mount of a missing file creates an empty directory).
- `bot/i18n.py` — the message catalog. `t("dotted.key", **params)` reads
  `config/messages.<LOCALE>.toml` (`tomllib`, stdlib) and formats with `str.format()`.
  **The boundary that matters: only text a Telegram user or admin sees is localized.**
  Operator-facing output — startup errors, log lines, `/healthz` problems — stays
  hardcoded English, because its audience runs the bot rather than uses it. `t()` raises
  on an unknown key instead of falling back; `tests/test_i18n.py` is what makes that safe
  (key and placeholder parity across locales, plus an AST sweep of every call site).
  Note `i18n` imports the `config` *module*, not `config.LOCALE` — `from ... import LOCALE`
  would bind the value at import time and make the locale unswappable in tests.
- `bot/db.py` — aiosqlite, file `bot.sqlite3` (gitignored). Tables `subscribers`
  (`user_id`, `username`, `full_name`) and `scheduled_broadcasts`. `init_db` adds missing
  columns to older databases via `PRAGMA table_info`.
- `bot/handlers/start.py` — `/start`: `add_subscriber` (with username and name) plus the greeting.
- `bot/handlers/broadcast.py` — the FSM wizard (`bot/states.py`): text → media → buttons →
  when (now/scheduled) → send. Admins only (`bot/filters.py: IsAdmin`). `_origin()` and
  `_bot()` narrow aiogram's optional types at the six callback sites.
- `bot/handlers/admin.py` — admin `/help` (from the catalog), `/stats` (count and list of
  subscribers), `/scheduled` and `/cancel_scheduled <id>`; long replies are split by the
  Telegram limit. `/stats` backfills empty `full_name` values via `getChat` (batches of 50),
  picking up names for anyone who subscribed before the column existed. Names come from the
  profile, so they go through `html.escape` (`parse_mode=HTML` is global).
- `bot/keyboards.py` — `parse_buttons` (`Label - link` lines, split on the **last** ` - `),
  `build_keyboard`, JSON serialisation for the database. Raises `ButtonParseError`, which
  carries a message *key* rather than a rendered string, so this module stays a pure,
  dependency-free unit and the handler decides which language to answer in.
- `bot/broadcaster.py` — `BroadcastPayload` plus `send_to`/`broadcast_to_all` (throttled to
  ~25 msg/s, drops subscribers who blocked the bot, handles flood-wait). One send path for
  both immediate and scheduled broadcasts.
- `bot/scheduler.py` — APScheduler polls `get_due` once a minute and sends what is due
  (survives restarts, no job store). Plus two probe jobs: `heartbeat` (every 30s) and
  `telegram_ping` (`getMe` every 5 minutes).
- `bot/health.py` — liveness probe: aiohttp server on `HEALTH_PORT` (8080), `GET /healthz`
  → 200, or 503 with a `problems` list. Unhealthy if the polling task died, the `loop`
  heartbeat is stale (>180s) or `telegram` is (>15 min), or the `due_broadcasts` job is
  paused. The `loop` heartbeat is its own job rather than a tick inside `_process_due`:
  that job has `max_instances=1`, and a long broadcast (25 msg/s) would occupy the slot and
  raise a false alarm. Thresholds are forgiven while `uptime` is below the limit, otherwise
  every deploy would fail in its first minute.
- `bot/timeutils.py` — lenient date/time parsing (Moscow): several formats, current year by
  default, time-only means today; comparison against `now`.

## Deployment

Push to `master` → `.github/workflows/deploy.yml`: run the shared checks, then SSH to the
VPS (`appleboy/ssh-action`), `git pull` in `/opt/chat_bot_calendar` and
`docker compose up -d --build`; the deploy waits up to 60s for a 200 from `/healthz` and
fails if it never arrives. The image is built from `Dockerfile` (base
`ghcr.io/astral-sh/uv`, `uv pip install --system`). `docker-compose.yml` passes
`BOT_TOKEN`/`ADMIN_IDS`/`LOCALE` through from the environment and mounts `./config` (ro,
holding `welcome.html` and the catalogs) and `./data` (SQLite, `DB_PATH=/app/data/bot.sqlite3`).
GitHub: secrets `VPS_HOST/VPS_USER/VPS_SSH_KEY/BOT_TOKEN`, variables `ADMIN_IDS` and `LOCALE`.

CI lives in `.github/workflows/checks.yml` (`workflow_call`: ruff, ruff format --check,
mypy, pytest) and is invoked by both `ci.yml` (pull requests and master) and `deploy.yml`,
so the two gates cannot drift. Master pushes therefore run the checks twice; that is
deliberate, so the README badge reflects master.

## Important details

- Broadcast text is taken as `message.html_text`, preserving Telegram's native formatting
  (bold/italic/links).
- Scheduled times are **Moscow** (`Europe/Moscow`), stored as the string
  `YYYY-MM-DD HH:MM:SS` and compared as strings (the format is fixed-width).
- The greeting after `/start` is sent only by the code — BotFather can show a Description
  only *before* Start is pressed.
- Avoid nouns that agree with a number in catalog strings. Prefer the label form
  ("Recipients: 5") over "5 recipients", which would need Russian plural rules.

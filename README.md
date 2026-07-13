# chat_bot_calendar

A Telegram broadcast bot built with aiogram 3.x. Users subscribe with `/start`, and an
administrator sends the same message (text, photo/video, inline buttons) to every
subscriber — either immediately or on a schedule.

## Requirements

- Python 3.13
- [uv](https://docs.astral.sh/uv/) (package manager)

## Setup

```bash
uv venv --python 3.13
uv pip install -r requirements.txt

cp .env.example .env                                 # set BOT_TOKEN and ADMIN_IDS
cp config/welcome.example.html config/welcome.html   # the /start greeting text

.venv/bin/python -m bot.main
```

`ADMIN_IDS` is a comma-separated list of Telegram user IDs (find yours via
[@userinfobot](https://t.me/userinfobot)).

## Usage

- Subscriber: `/start` — subscribe and receive the greeting.
- Admin (listed in `ADMIN_IDS`):
  - `/help` — list of admin commands (text from `config/help.html`).
  - `/broadcast` — step-by-step wizard (text → photo/video → buttons → now or scheduled);
    `/cancel` aborts the wizard.
  - `/stats` — subscriber count and list (id, username).
  - `/scheduled` — list pending scheduled broadcasts.
  - `/cancel_scheduled <id>` — cancel a pending scheduled broadcast.

Buttons are entered one per line as `Label - https://link`.

Scheduled time is Moscow time and accepts several formats: `24.06.2026 19:00`,
`24.06 19:00` (current year), or just `19:00` (today).

## Health check

The bot serves a liveness probe on `HEALTH_PORT` (default `8080`):

```bash
curl http://127.0.0.1:8080/healthz
{"status": "ok", "uptime": 3600, "last_tick": {"loop": 12, "telegram": 78}}
```

It answers **200** while the bot is alive and **503** with a `problems` list when it is
not — the update polling loop has stopped, the scheduler tick or the last successful
`getMe` has gone stale, or the scheduled-broadcast job is paused. This catches the
failure mode a restart policy cannot: the process is still up, but stuck.

Point an external monitor (Uptime Kuma, healthchecks.io, …) at
`http://<vps>:8080/healthz` with accepted status code `200`. Docker Compose also runs
the same check as a container `healthcheck`, so `docker compose ps` shows the state, and
the deploy fails if the bot does not report healthy within 60 seconds.

## Tests

```bash
.venv/bin/python -m pytest
```

## Deployment

Pushing to `master` triggers `.github/workflows/deploy.yml`: it runs the tests, then
SSHes into the VPS, pulls the latest code and restarts the container via Docker Compose.

One-time VPS setup:

```bash
git clone <repo-url> /opt/chat_bot_calendar
cd /opt/chat_bot_calendar
cp config/welcome.example.html config/welcome.html   # edit the greeting; gitignored, survives pulls
mkdir -p data                                        # SQLite lives here (persisted across deploys)
```

Configure in the GitHub repository:

- Secrets: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, `BOT_TOKEN`
- Variables: `ADMIN_IDS`

Run locally with Docker:

```bash
BOT_TOKEN=... ADMIN_IDS=... docker compose up -d --build
```

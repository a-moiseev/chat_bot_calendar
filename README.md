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

cp .env.example .env                   # set BOT_TOKEN (from @BotFather) and ADMIN_IDS
cp welcome.example.html welcome.html   # the /start greeting text

.venv/bin/python -m bot.main
```

`ADMIN_IDS` is a comma-separated list of Telegram user IDs (find yours via
[@userinfobot](https://t.me/userinfobot)).

## Usage

- Subscriber: `/start` — subscribe and receive the greeting.
- Admin (listed in `ADMIN_IDS`):
  - `/broadcast` — step-by-step wizard (text → photo/video → buttons → now or scheduled);
    `/cancel` aborts the wizard.
  - `/stats` — subscriber count and list (id, username).
  - `/scheduled` — list pending scheduled broadcasts.
  - `/cancel_scheduled <id>` — cancel a pending scheduled broadcast.

Buttons are entered one per line as `Label - https://link`.

Scheduled time is Moscow time and accepts several formats: `24.06.2026 19:00`,
`24.06 19:00` (current year), or just `19:00` (today).

## Tests

```bash
.venv/bin/python -m pytest
```

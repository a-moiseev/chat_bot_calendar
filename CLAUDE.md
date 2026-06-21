# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status

A Telegram chat bot built on **aiogram 3.x**, targeting **Python 3.13**. The bot logic itself is not written yet — only the dev environment and dependencies are set up.

## Environment

- Package manager: **uv** (using the `uv pip` workflow with `requirements.txt`, not `pyproject.toml`/`uv.lock`).
- `requirements.txt` holds both runtime and dev dependencies (dev tools are under the `# dev` comment).

```bash
uv venv --python 3.13          # create .venv
uv pip install -r requirements.txt
```

After adding/removing a dependency, pin it in `requirements.txt` to the installed version (`uv pip show <pkg>`).

## Commands

```bash
.venv/bin/python -m pytest     # run tests
.venv/bin/python -m pytest path/to/test_file.py::test_name   # single test
.venv/bin/ruff check .         # lint
.venv/bin/ruff format .        # format
.venv/bin/mypy .               # type-check
```

`pytest-asyncio` is installed for testing aiogram's async handlers.

## Notes

- The bot token is read from the environment via `python-dotenv` — keep it in `.env` (gitignored), never commit it.

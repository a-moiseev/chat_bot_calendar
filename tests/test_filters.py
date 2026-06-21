from types import SimpleNamespace

import bot.filters as filters
from bot.filters import IsAdmin


def _msg(user_id):
    user = SimpleNamespace(id=user_id) if user_id is not None else None
    return SimpleNamespace(from_user=user)


async def test_admin_passes(monkeypatch):
    monkeypatch.setattr(filters, "ADMIN_IDS", {42})
    assert await IsAdmin()(_msg(42)) is True


async def test_non_admin_blocked(monkeypatch):
    monkeypatch.setattr(filters, "ADMIN_IDS", {42})
    assert await IsAdmin()(_msg(7)) is False


async def test_no_user_blocked(monkeypatch):
    monkeypatch.setattr(filters, "ADMIN_IDS", {42})
    assert await IsAdmin()(_msg(None)) is False

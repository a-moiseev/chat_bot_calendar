import pytest

from bot import db


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """An isolated temporary database for one test."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.sqlite3")

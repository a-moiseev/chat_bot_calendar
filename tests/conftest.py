import pytest

from bot import db


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Изолированная временная БД для теста."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.sqlite3")

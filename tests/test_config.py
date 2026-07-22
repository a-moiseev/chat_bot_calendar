import pytest

from bot import config


def test_validate_requires_token(monkeypatch):
    monkeypatch.setattr(config, "BOT_TOKEN", "")
    monkeypatch.setattr(config, "ADMIN_IDS", {1})
    with pytest.raises(RuntimeError, match="BOT_TOKEN"):
        config.validate()


def test_validate_requires_admins(monkeypatch):
    monkeypatch.setattr(config, "BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ADMIN_IDS", set())
    with pytest.raises(RuntimeError, match="ADMIN_IDS"):
        config.validate()


def test_welcome_text_missing_file_explains_the_fix(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "WELCOME_FILE", tmp_path / "welcome.html")
    config.get_welcome_text.cache_clear()
    with pytest.raises(FileNotFoundError, match="welcome.example.html"):
        config.get_welcome_text()
    config.get_welcome_text.cache_clear()

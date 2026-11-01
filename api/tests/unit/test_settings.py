import pytest
from pydantic import ValidationError

from cinecircle_api.settings import Settings


def test_settings_require_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError, match="(?i)database_url"):
        Settings(_env_file=None)


def test_settings_reject_empty_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    with pytest.raises(ValidationError, match="(?i)database_url"):
        Settings(_env_file=None)


def test_cors_origins_parse_comma_list(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x@127.0.0.1:1/x")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173, https://cinecircle.onrender.com")
    s = Settings(_env_file=None)
    assert s.cors_origins == ["http://localhost:5173", "https://cinecircle.onrender.com"]
    assert s.app_env == "local"


def test_cors_origins_default(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x@127.0.0.1:1/x")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    assert Settings(_env_file=None).cors_origins == ["http://localhost:5173"]


def test_cors_origins_strip_trailing_slash(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x@127.0.0.1:1/x")
    monkeypatch.setenv("CORS_ORIGINS", "https://cinecircle.onrender.com/ , http://localhost:5173//")
    assert Settings(_env_file=None).cors_origins == [
        "https://cinecircle.onrender.com",
        "http://localhost:5173",
    ]

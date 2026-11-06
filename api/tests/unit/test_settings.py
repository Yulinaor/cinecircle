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


def test_supabase_settings_cleaned_and_blank_is_none(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x@127.0.0.1:1/x")
    monkeypatch.setenv("SUPABASE_URL", " http://127.0.0.1:55321/ ")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "  ")
    s = Settings(_env_file=None)
    assert s.supabase_url == "http://127.0.0.1:55321"
    assert s.supabase_jwt_secret is None
    monkeypatch.setenv("SUPABASE_URL", "")
    assert Settings(_env_file=None).supabase_url is None


def test_cors_origins_default(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x@127.0.0.1:1/x")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    assert Settings(_env_file=None).cors_origins == ["http://localhost:5173"]


def test_external_keys_optional_and_blank_is_none(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x@127.0.0.1:1/x")
    monkeypatch.setenv("TMDB_API_KEY", "  ")
    monkeypatch.delenv("OMDB_API_KEY", raising=False)
    s = Settings(_env_file=None)
    assert s.tmdb_api_key is None and s.omdb_api_key is None


def test_cors_origins_strip_trailing_slash(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x@127.0.0.1:1/x")
    monkeypatch.setenv("CORS_ORIGINS", "https://cinecircle.onrender.com/ , http://localhost:5173//")
    assert Settings(_env_file=None).cors_origins == [
        "https://cinecircle.onrender.com",
        "http://localhost:5173",
    ]


def test_app_env_defaults_to_production(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x@127.0.0.1:1/x")
    monkeypatch.delenv("APP_ENV", raising=False)
    assert Settings(_env_file=None).app_env == "production"
    monkeypatch.setenv("APP_ENV", "local")
    assert Settings(_env_file=None).app_env == "local"

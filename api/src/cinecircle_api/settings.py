"""Runtime configuration, read from environment variables (and api/.env when present)."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    database_url: str = Field(min_length=1, validation_alias="DATABASE_URL")
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default=["http://localhost:5173"], validation_alias="CORS_ORIGINS"
    )
    app_env: Literal["local", "test", "production"] = Field(
        default="local", validation_alias="APP_ENV"
    )
    # Backend-only catalogue keys; the app still starts without them (title endpoints answer 503).
    tmdb_api_key: str | None = Field(default=None, validation_alias="TMDB_API_KEY")
    omdb_api_key: str | None = Field(default=None, validation_alias="OMDB_API_KEY")
    # Supabase Auth. Without SUPABASE_URL every protected route answers 503 auth_unavailable.
    # The JWT secret is only for HS256 tokens (legacy projects); ES256/RS256 use the JWKS.
    supabase_url: str | None = Field(default=None, validation_alias="SUPABASE_URL")
    supabase_jwt_secret: str | None = Field(default=None, validation_alias="SUPABASE_JWT_SECRET")

    @field_validator("tmdb_api_key", "omdb_api_key", "supabase_jwt_secret", mode="before")
    @classmethod
    def _blank_key_is_none(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("supabase_url", mode="before")
    @classmethod
    def _clean_supabase_url(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().rstrip("/") or None
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.split(",")
        if isinstance(value, list):
            # Browsers send Origin with no trailing slash; dashboard-copied URLs often have one.
            origins = (str(origin).strip().rstrip("/") for origin in value)
            return [origin for origin in origins if origin]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()

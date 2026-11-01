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

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()

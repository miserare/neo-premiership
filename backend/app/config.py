from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, sourced from environment variables / a .env file."""

    project_name: str = "Pokémon Premiership"
    # Defaults to production so a deployment that forgets to set ENVIRONMENT
    # fails safe: development turns on SQLAlchemy's `echo`, which writes every
    # query - and its bound parameters - to the logs.
    environment: str = "production"

    database_url: str = "postgresql+asyncpg://neo_premiership:neo_premiership@localhost:5432/neo_premiership"

    # Comma-separated in the environment (e.g. "http://a.com,http://b.com"),
    # normalized into a list here so CORSMiddleware can consume it directly.
    cors_origins: list[str] = ["http://localhost:5173"]

    # Shared secret required (via the X-Admin-Token header) to reach any write
    # endpoint. No hardcoded default - if unset, admin routes fail closed with
    # a 503 rather than silently running open.
    admin_token: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

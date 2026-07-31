import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Values that look configured but are not. Production refuses to start on any of
# them, so a half-finished .env fails loudly instead of running with a guessable
# secret.
PLACEHOLDER_VALUES = frozenset(
    {
        "",
        "change-me",
        "change-me-admin-token",
        "changeme",
        "placeholder",
        "secret",
        "password",
        "dev-admin-token",
        "neo_premiership",
        "test-admin-token",
        "replace-me",
        "todo",
    }
)

# Secrets that may be delivered as a file path instead of an inline value, which
# is how Docker Compose secrets and most orchestrators present them.
FILE_BACKED_SETTINGS = ("SESSION_SECRET", "ADMIN_TOKEN", "DATABASE_URL", "POSTGRES_PASSWORD")

MIN_SESSION_SECRET_BYTES = 32


def _load_file_backed_secrets() -> None:
    """Promote FOO_FILE=/run/secrets/foo into FOO.

    Reading the file here keeps the secret out of the process environment of
    every child process and out of `docker inspect`, which shows environment
    variables but not file contents.
    """
    for name in FILE_BACKED_SETTINGS:
        path = os.environ.get(f"{name}_FILE")
        if not path:
            continue
        try:
            value = Path(path).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RuntimeError(f"{name}_FILE is set but {path} could not be read: {exc}") from exc
        if value:
            os.environ[name] = value


class Settings(BaseSettings):
    """Application configuration, sourced from environment variables / a .env file."""

    project_name: str = "Pokémon Premiership"
    # Defaults to production so a deployment that forgets to set ENVIRONMENT
    # fails safe: development turns on SQLAlchemy's `echo`, which writes every
    # query - and its bound parameters - to the logs.
    environment: str = "production"

    # Public hostname. Used for trusted-host validation and cookie policy.
    domain: str = "pk-prem.com"

    database_url: str = "postgresql+asyncpg://neo_premiership:neo_premiership@localhost:5432/neo_premiership"

    # Connection pool sizing for a 2 GB single-VPS deployment: small, with
    # pre-ping so a connection dropped by a database restart is discarded rather
    # than handed to a request.
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_pool_timeout_seconds: int = 10
    db_pool_recycle_seconds: int = 1800
    db_connect_timeout_seconds: int = 10

    # Empty in same-origin production: the browser calls /api on its own origin
    # via Caddy, so no cross-origin request exists to permit.
    cors_origins: list[str] = []

    # --- Session authentication -------------------------------------------
    session_secret: str | None = None
    session_ttl_hours: int = Field(default=12, ge=1, le=720)
    session_idle_timeout_minutes: int = Field(default=60, ge=5, le=1440)

    login_max_attempts: int = Field(default=5, ge=1)
    login_ip_max_attempts: int = Field(default=20, ge=1)
    login_lockout_minutes: int = Field(default=15, ge=1)

    # --- Legacy shared token (transitional only) --------------------------
    admin_token: str | None = None
    # Off by default. Must be switched on deliberately, and production refuses
    # to start with it enabled unless a token is actually configured.
    legacy_admin_token_enabled: bool = False

    # --- Transport / proxy -------------------------------------------------
    # X-Forwarded-* is only believed when the app is genuinely behind a proxy,
    # otherwise a client could spoof its source address past IP throttling.
    trust_proxy_headers: bool = False

    # --- API documentation -------------------------------------------------
    # Swagger/ReDoc/openapi.json describe every admin route. Off in production.
    docs_enabled: bool | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------------------------------------------------------------- helpers

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.environment.strip().lower() == "development"

    @property
    def sql_echo(self) -> bool:
        return self.is_development

    @property
    def cookies_secure(self) -> bool:
        """Secure cookies everywhere except local http development."""
        return not self.is_development

    @property
    def show_docs(self) -> bool:
        if self.docs_enabled is not None:
            return self.docs_enabled
        return not self.is_production

    @property
    def trusted_hosts(self) -> list[str]:
        if not self.is_production:
            return ["*"]
        return [self.domain, f"www.{self.domain}"]

    # ------------------------------------------------------------ validators

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            # Tolerate a JSON-style list as well as a comma-separated string.
            if stripped.startswith("["):
                import json

                return json.loads(stripped)
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def _validate_production(self) -> "Settings":
        if not self.is_production:
            return self

        problems: list[str] = []

        secret = (self.session_secret or "").strip()
        if secret.lower() in PLACEHOLDER_VALUES:
            problems.append("SESSION_SECRET is missing or a placeholder value")
        elif len(secret.encode("utf-8")) < MIN_SESSION_SECRET_BYTES:
            problems.append(
                f"SESSION_SECRET must be at least {MIN_SESSION_SECRET_BYTES} bytes "
                f"(got {len(secret.encode('utf-8'))})"
            )

        url = self.database_url
        if "localhost" in url or "127.0.0.1" in url:
            problems.append("DATABASE_URL points at localhost, which is a development database")
        for placeholder in ("neo_premiership:neo_premiership", "change-me", "postgres:postgres"):
            if placeholder in url:
                problems.append("DATABASE_URL still contains development credentials")
                break
        if not url.startswith("postgresql+asyncpg://"):
            problems.append("DATABASE_URL must use the postgresql+asyncpg driver")

        if not self.domain or self.domain.strip().lower() in PLACEHOLDER_VALUES:
            problems.append("DOMAIN is missing or a placeholder value")

        if self.legacy_admin_token_enabled:
            token = (self.admin_token or "").strip()
            if token.lower() in PLACEHOLDER_VALUES:
                problems.append(
                    "LEGACY_ADMIN_TOKEN_ENABLED is on but ADMIN_TOKEN is missing or a placeholder"
                )
            elif len(token) < 32:
                problems.append("ADMIN_TOKEN must be at least 32 characters when the legacy path is on")

        for origin in self.cors_origins:
            if origin == "*":
                problems.append("CORS_ORIGINS must not be '*' in production")
            elif origin.startswith("http://"):
                problems.append(f"CORS origin {origin} is plaintext http in production")

        if problems:
            raise ValueError(
                "Refusing to start in production with an unsafe configuration:\n  - "
                + "\n  - ".join(problems)
            )
        return self


@lru_cache
def get_settings() -> Settings:
    _load_file_backed_secrets()
    return Settings()


settings = get_settings()

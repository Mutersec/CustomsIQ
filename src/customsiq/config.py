"""Application configuration, loaded from environment variables / .env."""

from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_POSTGRES_SCHEMES = ("postgres://", "postgresql://")


class Settings(BaseSettings):
    """Runtime configuration for CustomsIQ.

    Values are read from environment variables prefixed with `CUSTOMSIQ_`,
    or from a `.env` file in the working directory (see `.env.example`).

    Database backend precedence: `CUSTOMSIQ_DATABASE_URL` (a PostgreSQL URL),
    if set, wins over `CUSTOMSIQ_DATABASE_PATH` (a SQLite file). Unset, the
    app uses SQLite exactly as it always has — see `database_target`.
    """

    model_config = SettingsConfigDict(env_file=".env", env_prefix="CUSTOMSIQ_")

    database_path: str = "customsiq.db"
    database_url: Optional[str] = None
    log_level: str = "INFO"
    screening_threshold: float = 0.75

    @field_validator("database_url")
    @classmethod
    def _postgres_url_only(cls, value: Optional[str]) -> Optional[str]:
        """Treat an empty value as unset; reject anything that isn't a Postgres URL."""
        if value is None or not value.strip():
            return None
        if not value.startswith(_POSTGRES_SCHEMES):
            raise ValueError("CUSTOMSIQ_DATABASE_URL must start with postgresql:// or postgres://")
        return value

    @property
    def database_target(self) -> str:
        """What to hand `get_connection`: the Postgres URL if set, else the SQLite path."""
        return self.database_url or self.database_path


settings = Settings()

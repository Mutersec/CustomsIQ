"""Application configuration, loaded from environment variables / .env."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for CustomsIQ.

    Values are read from environment variables prefixed with `CUSTOMSIQ_`,
    or from a `.env` file in the working directory (see `.env.example`).
    """

    model_config = SettingsConfigDict(env_file=".env", env_prefix="CUSTOMSIQ_")

    database_path: str = "customsiq.db"
    log_level: str = "INFO"


settings = Settings()

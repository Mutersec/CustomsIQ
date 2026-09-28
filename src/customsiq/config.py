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

    # PBKDF2-HMAC-SHA256 work factor. 600_000 is OWASP's current recommendation
    # for SHA-256 and costs ~160 ms per hash here; the test suite lowers it in
    # tests/conftest.py so 40+ auth tests don't spend ten seconds in the KDF.
    password_iterations: int = 600_000
    session_ttl_hours: int = 12
    seed_demo_users: bool = True

    # Role granted by self-service registration. `viewer` — read the audit
    # trail, nothing else — because anyone on the internet can call
    # POST /auth/register: the role it hands out is the privilege boundary
    # between "stranger" and "can write to the compliance audit trail", and
    # review rows are append-only with no delete route. A deployment that
    # wants the old demo behaviour can still set CUSTOMSIQ_SELF_REGISTRATION_ROLE.
    self_registration_role: str = "viewer"

    # Invoice upload limits. The size cap is enforced while streaming the body,
    # not from Content-Length, and the rate limit is per account, per process.
    upload_max_bytes: int = 2_097_152
    upload_rate_limit_per_minute: int = 10

    # Per-IP rate limits, per process. Auth routes have no authenticated
    # principal to key on, so these are the pre-auth brake; the search routes
    # are capped because each one is a linear scan over the whole nomenclature
    # and is reachable anonymously.
    auth_rate_limit_per_minute: int = 10
    search_rate_limit_per_minute: int = 30

    # Interactive API docs (/docs, /redoc, /openapi.json). Off by default: the
    # whole API sits behind sign-in, and a public schema is a map of every
    # route for anyone probing it. Turn on for local development only.
    enable_api_docs: bool = False

    # Sign-up e-mail verification. Codes are sent through Brevo's HTTP API
    # (free tier, 300 mails/day) because Render's free instances cannot open
    # outbound SMTP connections. `mail_from` must be a sender or domain
    # verified in Brevo. With no API key, registration fails closed — unless
    # `mail_dev_log_codes` is set, which writes codes to the server log for
    # local development. Never enable that on a public deployment.
    brevo_api_key: Optional[str] = None
    mail_from: str = "noreply@customsiq.org"
    mail_from_name: str = "CustomsIQ"
    mail_dev_log_codes: bool = False
    verification_code_ttl_minutes: int = 10
    verification_max_attempts: int = 5
    verification_resend_seconds: int = 60

    # "Sign in with Google". The OAuth client ID from Google Cloud Console
    # (type: Web application). Unset, the Google button is simply not shown.
    google_client_id: Optional[str] = None

    @field_validator("database_url")
    @classmethod
    def _postgres_url_only(cls, value: Optional[str]) -> Optional[str]:
        """Treat an empty value as unset; reject anything that isn't a Postgres URL."""
        if value is None or not value.strip():
            return None
        if not value.startswith(_POSTGRES_SCHEMES):
            raise ValueError("CUSTOMSIQ_DATABASE_URL must start with postgresql:// or postgres://")
        return value

    @field_validator("brevo_api_key", "google_client_id")
    @classmethod
    def _blank_is_unset(cls, value: Optional[str]) -> Optional[str]:
        """An empty environment variable means "not configured", not an empty key."""
        if value is None or not value.strip():
            return None
        return value.strip()

    @property
    def database_target(self) -> str:
        """What to hand `get_connection`: the Postgres URL if set, else the SQLite path."""
        return self.database_url or self.database_path


settings = Settings()

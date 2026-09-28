"""Custom exceptions for CustomsIQ."""


class CustomsIQError(Exception):
    """Base class for all CustomsIQ errors."""


class InvalidQueryError(CustomsIQError):
    """Raised when user input is unusable: blank, too long, or malformed."""


class HSCodeNotFoundError(CustomsIQError):
    """Raised when a lookup by exact HS code finds no match."""


class AuthenticationError(CustomsIQError):
    """Raised when a caller is not signed in, or signed in with a stale session.

    Distinct from PermissionDeniedError: this means "we don't know who you are"
    (HTTP 401), not "we know who you are and it isn't enough" (HTTP 403).
    """


class PermissionDeniedError(CustomsIQError):
    """Raised when an authenticated user's role doesn't cover the action."""


class RateNotFoundError(CustomsIQError):
    """Raised when no duty rate is stored for an HS code.

    Distinct from a zero rate: this is a gap in the tariff data, and treating
    it as duty-free would understate what an importer owes.
    """


class VerificationCooldownError(CustomsIQError):
    """Raised when a new verification code is requested too soon after the last.

    Mapped to HTTP 429. Carries how long the caller has to wait.
    """

    def __init__(self, retry_after: int) -> None:
        super().__init__(f"please wait {retry_after} seconds before requesting a new code")
        self.retry_after = retry_after

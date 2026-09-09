"""Custom exceptions for CustomsIQ."""


class CustomsIQError(Exception):
    """Base class for all CustomsIQ errors."""


class InvalidQueryError(CustomsIQError):
    """Raised when user input is unusable: blank, too long, or malformed."""


class HSCodeNotFoundError(CustomsIQError):
    """Raised when a lookup by exact HS code finds no match."""


class RateNotFoundError(CustomsIQError):
    """Raised when no duty rate is stored for an HS code.

    Distinct from a zero rate: this is a gap in the tariff data, and treating
    it as duty-free would understate what an importer owes.
    """

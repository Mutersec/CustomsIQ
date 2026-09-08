"""Custom exceptions for CustomsIQ."""


class CustomsIQError(Exception):
    """Base class for all CustomsIQ errors."""


class InvalidQueryError(CustomsIQError):
    """Raised when a search query is empty, blank, or too long."""


class HSCodeNotFoundError(CustomsIQError):
    """Raised when a lookup by exact HS code finds no match."""

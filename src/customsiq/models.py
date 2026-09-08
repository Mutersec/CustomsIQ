"""Data models for HS (GTİP) code records."""

from dataclasses import dataclass


@dataclass(frozen=True)
class HSCode:
    """A single Harmonized System (GTİP) tariff code entry.

    Attributes:
        code: Numeric HS/GTİP code (e.g. "8517120000").
        description: Human-readable product description.
        category: Broad product category (e.g. "Electronics").
    """

    code: str
    description: str
    category: str

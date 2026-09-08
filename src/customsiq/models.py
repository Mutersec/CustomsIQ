"""Data models for HS/CN code records."""

from dataclasses import dataclass


@dataclass(frozen=True)
class HSCode:
    """A single Combined Nomenclature (CN/TARIC) tariff code entry.

    Attributes:
        code: Numeric CN/TARIC code (e.g. "8517120000").
        description: Human-readable product description.
        category: Broad product category (e.g. "Electronics").
    """

    code: str
    description: str
    category: str

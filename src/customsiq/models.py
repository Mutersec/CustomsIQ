"""Data models for HS/CN code records and sanctions screening."""

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


@dataclass(frozen=True)
class SanctionedEntity:
    """A single denied-party record from a sanctions list.

    Attributes:
        name: Entity name as published on the list.
        country: ISO 3166-1 alpha-2 country code (e.g. "CY").
        list_source: Name of the list the entry comes from.
        date_added: ISO 8601 date the entry was listed (SQLite has no date type).
    """

    name: str
    country: str
    list_source: str
    date_added: str

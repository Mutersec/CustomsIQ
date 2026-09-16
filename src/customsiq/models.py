"""Data models for HS/CN codes, sanctions screening and tariff rates."""

from dataclasses import dataclass
from typing import Optional


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


@dataclass(frozen=True)
class ReviewDecision:
    """A human reviewer's sign-off on one automated decision (audit trail).

    Attributes:
        id: Autoincrement row id (audit rows have no natural key).
        subject_type: "classification" | "screening" | "duty".
        subject_reference: Deterministic hash identifying the reviewed input.
        decision: "approved" | "rejected" | "flagged".
        reviewer_name: Free text — stand-in until authenticated users exist.
        comment: Optional free-text note.
        reviewed_at: ISO 8601 timestamp the decision was recorded.
    """

    id: int
    subject_type: str
    subject_reference: str
    decision: str
    reviewer_name: str
    comment: Optional[str]
    reviewed_at: str


@dataclass(frozen=True)
class TariffRate:
    """A duty rate applicable to one HS code for one origin.

    Attributes:
        hs_code: The CN/TARIC code the rate applies to.
        country_of_origin: ISO 3166-1 alpha-2 origin code, or ALL_ORIGINS for a
            standard rate that applies regardless of origin.
        rate_type: "standard" (MFN) or "preferential".
        rate_percent: Duty rate as a percentage of the customs value.
        trade_agreement: Agreement granting a preferential rate; None for standard.
        valid_from: ISO 8601 date the rate takes effect.
    """

    hs_code: str
    country_of_origin: str
    rate_type: str
    rate_percent: float
    trade_agreement: Optional[str]
    valid_from: str

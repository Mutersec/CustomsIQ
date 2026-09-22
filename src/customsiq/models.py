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
        reviewer_name: Who signed off. For API submissions this is the
            authenticated user's username, set by the server, never by the
            client. CLI submissions and rows written before authenticated
            users existed hold free text; `review_authorship` is what says
            which of the two a row is, and it is keyed by row id so a free-text
            name can never be claimed by someone registering it later.
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
class HSCodeVersion:
    """One SCD Type 2 version of an HS code's description/category over time.

    Attributes:
        id: Autoincrement row id (history rows have no natural key).
        code: The CN/TARIC code this version belongs to.
        description: The description as it read during this version's validity.
        category: The category as it read during this version's validity.
        valid_from: ISO 8601 timestamp this version became current.
        valid_to: ISO 8601 timestamp this version was superseded, or None if current.
        version_label: The import run that produced this version (e.g. "CN2026").
    """

    id: int
    code: str
    description: str
    category: str
    valid_from: str
    valid_to: Optional[str]
    version_label: str


@dataclass(frozen=True)
class ImportRun:
    """One run of scripts/import_cn_codes.py (the cn_code_versions audit log).

    Attributes:
        id: Autoincrement row id.
        version_label: Label identifying the run (e.g. "CN2026").
        source_description: The imported file's name, if known.
        imported_at: ISO 8601 timestamp the run completed.
        row_count: Number of leaf CN code records processed in this run.
    """

    id: int
    version_label: str
    source_description: Optional[str]
    imported_at: str
    row_count: int


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


@dataclass(frozen=True)
class User:
    """An account that can sign in and sign off on decisions.

    Attributes:
        id: Autoincrement row id.
        username: Unique login name; also what lands in
            `review_decisions.reviewer_name` for that user's sign-offs.
        role: "viewer" | "analyst" | "compliance_officer" | "admin".
        created_at: ISO 8601 timestamp the account was created.

    The password hash is deliberately absent: this record is handed to route
    handlers and serialized into responses, so the hash has no business
    travelling with it. `database.get_password_hash` fetches it on its own for
    the one function that verifies a login.
    """

    id: int
    username: str
    role: str
    created_at: str

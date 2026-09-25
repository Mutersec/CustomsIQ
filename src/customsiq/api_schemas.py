"""Pydantic response models for every JSON-returning route in api.py.

Typing only — no logic. Each model is built directly from the field set the
matching route already constructs by hand (a literal `return {...}` there),
so the JSON a client receives is unchanged; only `/openapi.json` and `/docs`
gain real schemas instead of `additionalProperties: true`. A test diffs each
route's response body before and after this module existed, which is the
actual guarantee that this is a presentation change, not a behavioural one —
see `tests/test_api_schemas.py`.

Field names mostly stay snake_case, matching the routes' existing dicts. The
two SAP GTS models are the one exception: `sap_gts_bridge.py` renders real
BAPIRET2 field names (`TYPE`, `NUMBER`, `MESSAGE_V1`, ...) and a `HEADER`/
`RETURN` envelope deliberately, because that vocabulary is the point of that
feature — see Phase 10's README section. Reproducing that here, uppercase
field names included, is what makes `/openapi.json` show the real BAPIRET2
shape to a reviewer who knows what to look for.
"""

from typing import Optional

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """GET /health"""

    service: str
    docs: str
    status: str


class SearchResult(BaseModel):
    """One item of GET /search's response."""

    code: str
    description: str
    category: str
    score: float


class ClassificationResultResponse(BaseModel):
    """One item of GET /classify's response."""

    code: str
    description: str
    category: str
    score: float
    matched_terms: list[str]
    subject_reference: str


class ScreeningResultResponse(BaseModel):
    """One item of GET /screen's response."""

    name: str
    country: str
    list_source: str
    date_added: str
    score: float
    subject_reference: str


class DutyCalculationResponse(BaseModel):
    """GET /calculate-duty"""

    hs_code: str
    country_of_origin: str
    customs_value: float
    rate_percent: float
    rate_type: str
    trade_agreement: Optional[str]
    duty_amount: float
    total_payable: float
    explanation: str
    subject_reference: str


class RiskFactorResponse(BaseModel):
    """One entry of RiskAssessmentResponse.factors."""

    name: str
    score: float
    weight: float
    explanation: str


class RiskAssessmentResponse(BaseModel):
    """GET /assess-risk"""

    level: str
    composite_score: float
    hs_code: Optional[str]
    factors: list[RiskFactorResponse]


class ExtractedFieldResponse(BaseModel):
    """One entry of ExtractionResultResponse.fields."""

    name: str
    value: str
    label: str
    source_line: str


class ExtractionResultResponse(BaseModel):
    """POST /extract-invoice"""

    fields: list[ExtractedFieldResponse]
    missing: list[str]
    completeness: float
    page_count: int
    has_text_layer: bool
    notes: list[str]


class GtsHeader(BaseModel):
    """The HEADER block of a GET /sap-gts/* response.

    Field names are uppercase because they mirror SAP GTS's own vocabulary —
    see sap_gts_bridge.py's module docstring for why that is a deliberate,
    labelled simulation rather than a real integration claim.
    """

    DOCUMENT_TYPE: str
    FUNCTIONAL_AREAS: list[str]
    DOCUMENT_STATUS: str
    SUBJECT_REFERENCE: str
    SOURCE_SYSTEM: str
    GENERATED_AT: str
    SIMULATION: bool
    DISCLAIMER: str


class GtsReturnRow(BaseModel):
    """One row of a GET /sap-gts/* response's RETURN table — the real BAPIRET2
    field names and shape, reproduced deliberately (see sap_gts_bridge.py)."""

    TYPE: str
    ID: str
    NUMBER: str
    MESSAGE: str
    LOG_NO: str
    LOG_MSG_NO: str
    MESSAGE_V1: str
    MESSAGE_V2: str
    MESSAGE_V3: str
    MESSAGE_V4: str
    PARAMETER: str
    ROW: int
    FIELD: str
    SYSTEM: str


class GtsDocumentResponse(BaseModel):
    """GET /sap-gts/compliance-check and GET /sap-gts/legal-control/{subject_reference}"""

    HEADER: GtsHeader
    RETURN: list[GtsReturnRow]


class HSCodeVersionResponse(BaseModel):
    """One entry of GET /codes/{code}/history's response."""

    code: str
    description: str
    category: str
    valid_from: str
    valid_to: Optional[str]
    version_label: str


class CodeTranslationsResponse(BaseModel):
    """GET /codes/{code}/translations"""

    code: str
    en: str
    de: Optional[str]
    fr: Optional[str]


class UserResponse(BaseModel):
    """The public shape of an account — never carries a password hash.

    Returned by /auth/register, /auth/login, /auth/users, and nested inside
    WhoAmIResponse.
    """

    username: str
    role: str
    created_at: str


class LogoutResponse(BaseModel):
    """POST /auth/logout"""

    signed_out: bool


class WhoAmIResponse(BaseModel):
    """GET /auth/me — `user` is null when nobody is signed in."""

    user: Optional[UserResponse]


class RoleChangeResponse(BaseModel):
    """POST /auth/users/{username}/role"""

    username: str
    role: str


class ReviewResponse(BaseModel):
    """POST /review, and one item of GET /review/history's and
    DashboardStatsResponse.recent_reviews's responses."""

    id: int
    subject_type: str
    subject_reference: str
    decision: str
    reviewer_name: str
    comment: Optional[str]
    reviewed_at: str
    authenticated: bool


class ImportRunResponse(BaseModel):
    """One entry of DashboardStatsResponse.recent_import_runs."""

    version_label: str
    source_description: Optional[str]
    imported_at: str
    row_count: int
    changed_count: int
    unchanged_count: int


class DashboardStatsResponse(BaseModel):
    """GET /dashboard/stats"""

    hs_code_count: int
    sanctioned_entity_count: int
    tariff_rate_count: int
    review_total: int
    review_by_decision: dict[str, int]
    review_by_subject_type: dict[str, int]
    recent_reviews: list[ReviewResponse]
    recent_reviews_restricted: bool
    import_run_count: int
    recent_import_runs: list[ImportRunResponse]
    versioned_code_count: int

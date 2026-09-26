"""FastAPI HTTP surface for CN code search, sanctions screening and duty calculation."""

import sqlite3
import time
from collections.abc import Callable
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from src.customsiq import auth, review, sap_gts_bridge
from src.customsiq.api_schemas import (
    ClassificationResultResponse,
    CodeTranslationsResponse,
    DashboardStatsResponse,
    DutyCalculationResponse,
    ExtractionResultResponse,
    GtsDocumentResponse,
    HealthResponse,
    HSCodeVersionResponse,
    LogoutResponse,
    ReviewResponse,
    RiskAssessmentResponse,
    RoleChangeResponse,
    ScreeningResultResponse,
    SearchResult,
    UserResponse,
    WhoAmIResponse,
)
from src.customsiq.cn_classifier import classify
from src.customsiq.config import settings
from src.customsiq.dashboard import get_dashboard_stats
from src.customsiq.database import (
    fetch_hs_code_history,
    fetch_translations,
    fetch_users,
    get_by_code,
    get_connection,
    load_bundled_cn_nomenclature,
    seed,
    update_user_role,
)
from src.customsiq.document_extraction import PDF_MAGIC, extract_invoice
from src.customsiq.embargo_screener import screen_entity
from src.customsiq.exceptions import (
    AuthenticationError,
    HSCodeNotFoundError,
    InvalidQueryError,
    RateNotFoundError,
)
from src.customsiq.models import User
from src.customsiq.risk import assess_shipment
from src.customsiq.search import search
from src.customsiq.tariff_calculator import calculate_duty

app = FastAPI(
    title="CustomsIQ",
    description=(
        "An EU trade-compliance toolkit — HS/CN classification, denied-party "
        "screening, duty calculation and composite risk scoring, on the real "
        "EU Combined Nomenclature."
    ),
    version="1.0.0",
)

# Resolved from this module, not the working directory: the deployed process
# may be started from anywhere, and a missing directory would raise on import.
_STATIC_DIR = Path(__file__).parent / "static"

_conn: sqlite3.Connection = get_connection(settings.database_target)
seed(_conn)
# Adds the real EU Combined Nomenclature 2026 on top of the 20-row mock
# SAMPLE_DATA seed() just wrote — not instead of it. The bundle is committed
# to the repo (data/cn_nomenclature_2026.csv), so this needs no network
# access and survives every cold start; upsert_hs_codes is idempotent, so
# re-running this on every restart is safe and cheap (~90 ms).
load_bundled_cn_nomenclature(_conn)
if settings.seed_demo_users:
    auth.seed_demo_users(_conn)

app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.middleware("http")
async def add_security_headers(request: Request, call_next: Callable) -> Response:
    """Attach a small set of low-effort, broadly-applicable security headers.

    Applied globally, including to error responses — a 400/404 needs these
    exactly as much as a 200 does, since they're about how the *browser*
    treats the response, not about what the response says.

    Deliberately not a Content-Security-Policy: the frontend is one file with
    a large inline <script>/<style> block, so a CSP strict enough to mean
    anything would need 'unsafe-inline' on both script-src and style-src
    (defeating most of what a CSP is for) or a restructuring of the frontend
    into external files, which is real, separate work outside "low-effort
    headers". Shipping a CSP that's security theater would be worse than
    naming the gap, so it's left out on purpose.
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Modern guidance is to explicitly disable this legacy header rather than
    # enable it — on some older browsers, enabling it was itself an XSS vector.
    response.headers["X-XSS-Protection"] = "0"
    return response


SESSION_COOKIE = "customsiq_session"


def current_user(request: Request) -> Optional[User]:
    """Resolve the signed-in user from the session cookie, or None.

    A dependency rather than middleware: most routes here are public, so
    identity is something a handler asks for, not a gate every request pays.
    """
    return auth.user_for_token(_conn, request.cookies.get(SESSION_COOKIE))


def require_permission(action: str) -> Callable[[Optional[User]], User]:
    """Build a dependency that admits only users whose role covers `action`.

    Returns 401 when nobody is signed in and 403 when someone is but ranks too
    low — the distinction matters to a client deciding whether to show a login
    form or an explanation.
    """

    def dependency(user: Optional[User] = Depends(current_user)) -> User:
        if user is None:
            raise HTTPException(status_code=401, detail="Sign in to perform this action.")
        if not auth.can(user.role, action):
            raise HTTPException(
                status_code=403,
                detail=f"Role '{user.role}' is not permitted to perform this action.",
            )
        return user

    return dependency


def _set_session_cookie(request: Request, response: Response, token: str) -> None:
    """Attach the session cookie.

    HttpOnly so script can't read it, SameSite=Lax so a cross-site POST never
    carries it (which is this app's CSRF defence), and Secure only when the
    request actually arrived over HTTPS — checked via X-Forwarded-Proto first,
    because the live deployment terminates TLS at a proxy and the app itself
    sees plain HTTP. A hardcoded Secure would break http://localhost.
    """
    forwarded = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
    is_https = (forwarded or request.url.scheme) == "https"
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        samesite="lax",
        secure=is_https,
        path="/",
    )


def _user_payload(user: User) -> dict:
    """Serialize a user for a response. The password hash isn't on this record."""
    return {"username": user.username, "role": user.role, "created_at": user.created_at}


@app.get("/", response_class=FileResponse, include_in_schema=False)
def index() -> FileResponse:
    """Serve the single-page web frontend.

    An explicit route rather than mounting StaticFiles at "/", which would be
    greedy enough to shadow /docs and the API routes.
    """
    return FileResponse(_STATIC_DIR / "index.html")


@app.get("/login", response_class=FileResponse, include_in_schema=False)
def login_page() -> FileResponse:
    """Serve the dedicated sign-in page, separate from the main app."""
    return FileResponse(_STATIC_DIR / "login.html")


@app.get("/health", response_model=HealthResponse)
def health() -> dict:
    """Liveness check and basic service info."""
    return {"service": "CustomsIQ API", "docs": "/docs", "status": "running"}


@app.get("/search", response_model=list[SearchResult])
def search_hs_codes(
    q: str = Query(..., description="Free-text product description"),
    limit: int = Query(5, ge=1, le=50),
) -> list[dict]:
    """Return the HS codes whose description best matches `q`.

    Reuses `src.customsiq.search.search`, the same function the CLI calls,
    so ranking logic is defined in exactly one place.
    """
    try:
        results = search(_conn, q, limit=limit)
    except InvalidQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [
        {
            "code": r.hs_code.code,
            "description": r.hs_code.description,
            "category": r.hs_code.category,
            "score": r.score,
        }
        for r in results
    ]


@app.get("/classify", response_model=list[ClassificationResultResponse])
def classify_description(
    description: str = Query(..., description="Free-text description of the goods"),
    top_n: int = Query(5, ge=1, le=50),
) -> list[dict]:
    """Suggest the CN codes a description most likely belongs to, with reasoning.

    Complements `/search`: that ranks by character overlap for a quick lookup,
    while this weighs how rare each term is across the corpus and reports which
    terms drove each suggestion.
    """
    try:
        results = classify(_conn, description, top_n=top_n)
    except InvalidQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [
        {
            "code": r.hs_code.code,
            "description": r.hs_code.description,
            "category": r.hs_code.category,
            "score": r.score,
            "matched_terms": r.matched_terms,
            "subject_reference": review.reference_for_classification(description),
        }
        for r in results
    ]


@app.get("/screen", response_model=list[ScreeningResultResponse])
def screen_name(
    name: str = Query(..., description="Person or organisation name to screen"),
) -> list[dict]:
    """Return every sanctioned entity that `name` may refer to.

    Reuses `src.customsiq.embargo_screener.screen_entity`, the same function
    the CLI calls, so screening logic is defined in exactly one place.
    """
    try:
        matches = screen_entity(_conn, name)
    except InvalidQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [
        {
            "name": m.entity.name,
            "country": m.entity.country,
            "list_source": m.entity.list_source,
            "date_added": m.entity.date_added,
            "score": m.score,
            "subject_reference": review.reference_for_screening(name),
        }
        for m in matches
    ]


@app.get("/calculate-duty", response_model=DutyCalculationResponse)
def calculate_duty_for_consignment(
    hs_code: str = Query(..., description="CN-8 or TARIC-10 code"),
    country_of_origin: str = Query(..., description="ISO 3166-1 alpha-2 origin code"),
    customs_value: float = Query(..., description="Declared customs value"),
) -> dict:
    """Return the duty owed on a consignment, and the rate that produced it.

    Reuses `src.customsiq.tariff_calculator.calculate_duty`, the same function
    the CLI calls, so rate selection is defined in exactly one place.
    """
    try:
        result = calculate_duty(_conn, hs_code, country_of_origin, customs_value)
    except InvalidQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "hs_code": result.hs_code,
        "country_of_origin": result.country_of_origin,
        "customs_value": float(result.customs_value),
        "rate_percent": result.rate_percent,
        "rate_type": result.rate_type,
        "trade_agreement": result.trade_agreement,
        "duty_amount": float(result.duty_amount),
        "total_payable": float(result.total_payable),
        "explanation": result.explanation,
        "explanation_key": result.explanation_key,
        "explanation_params": result.explanation_params,
        "subject_reference": review.reference_for_duty(hs_code, country_of_origin, customs_value),
    }


@app.get("/assess-risk", response_model=RiskAssessmentResponse)
def assess_risk(
    country_of_origin: str = Query(..., description="ISO 3166-1 alpha-2 origin code"),
    party_name: str = Query(..., description="Person or organisation to screen"),
    customs_value: float = Query(..., description="Declared customs value"),
    description: Optional[str] = Query(None, description="Free-text description of the goods"),
    hs_code: Optional[str] = Query(None, description="CN-8 or TARIC-10 code, if already known"),
) -> dict:
    """Return a composite risk assessment combining classification, screening and duty.

    Reuses `src.customsiq.risk.assess_shipment`, which itself only calls the
    existing `classify`, `screen_entity` and `calculate_duty` functions — this
    is a composing layer, not a new decision.
    """
    try:
        result = assess_shipment(
            _conn, country_of_origin, party_name, customs_value, description, hs_code
        )
    except InvalidQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "level": result.level,
        "composite_score": result.composite_score,
        "hs_code": result.hs_code,
        "factors": [
            {
                "name": f.name,
                "score": f.score,
                "weight": f.weight,
                "explanation": f.explanation,
                "explanation_key": f.explanation_key,
                "explanation_params": f.explanation_params,
            }
            for f in result.factors
        ],
    }


#: Upload timestamps per account, for the rate limit below. Application memory
#: only: this deliberately touches no database, so it behaves identically on the
#: SQLite and PostgreSQL backends and a backend switch can neither bypass nor
#: duplicate it.
_UPLOAD_HITS: dict = {}

_RATE_WINDOW_SECONDS = 60.0


def _check_rate_limit(username: str) -> None:
    """Allow N uploads per account per minute, or raise 429.

    # ponytail: one dict per process, cleared by a restart — right for the one
    # instance this runs on, and the wrong shape the moment there are two (each
    # would allow the full quota). Shared state (Redis, or a table) is the
    # upgrade path if a second instance ever appears.
    """
    now = time.monotonic()
    recent = [hit for hit in _UPLOAD_HITS.get(username, []) if now - hit < _RATE_WINDOW_SECONDS]
    if len(recent) >= settings.upload_rate_limit_per_minute:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Too many uploads. The limit is "
                f"{settings.upload_rate_limit_per_minute} per minute."
            ),
        )
    recent.append(now)
    _UPLOAD_HITS[username] = recent


async def _read_capped_body(request: Request) -> bytes:
    """Read the request body, refusing anything over the configured cap.

    Counted over the incoming chunks and aborted the moment the cap is passed,
    rather than buffering the whole body and checking Content-Length after the
    fact — a header can lie, and buffering first is exactly the bug worth not
    having on the one endpoint that accepts arbitrary bytes.
    """
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > settings.upload_max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File is too large (limit {settings.upload_max_bytes // 1024} KB).",
            )
    return bytes(body)


@app.post("/extract-invoice", response_model=ExtractionResultResponse)
async def extract_invoice_upload(
    request: Request,
    user: User = Depends(require_permission("document:extract")),
) -> dict:
    """Read an uploaded invoice PDF and return the fields found in it.

    Send the PDF as the raw request body (`Content-Type: application/pdf`).

    This endpoint deliberately does **not** classify, price or score anything.
    It returns fields for the user to review and edit in the existing forms,
    which then call the existing `/classify`, `/calculate-duty` and
    `/assess-risk` routes — thin composable pieces rather than one opaque
    action that decides on a document's behalf.

    The upload is never stored: the bytes live in memory for this request only.
    Requires a signed-in account (any role); anonymous callers are refused
    before a single byte is read.
    """
    _check_rate_limit(user.username)
    data = await _read_capped_body(request)

    # Content decides the type, never the filename or a declared Content-Type.
    if not data.startswith(PDF_MAGIC):
        raise HTTPException(status_code=415, detail="Only PDF files are supported.")

    try:
        # Off the event loop: parsing is CPU-bound, and this route is async only
        # because streaming the body requires it.
        result = await run_in_threadpool(extract_invoice, data)
    except InvalidQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "fields": [
            {
                "name": field.name,
                "value": field.value,
                "label": field.label,
                "source_line": field.source_line,
            }
            for field in result.fields
        ],
        "missing": result.missing,
        "completeness": result.completeness,
        "page_count": result.page_count,
        "has_text_layer": result.has_text_layer,
        "notes": result.notes,
    }


@app.get("/sap-gts/compliance-check", response_model=GtsDocumentResponse)
def sap_gts_compliance_check(
    country_of_origin: str = Query(..., description="ISO 3166-1 alpha-2 origin code"),
    party_name: str = Query(..., description="Person or organisation to screen"),
    customs_value: float = Query(..., description="Declared customs value"),
    description: Optional[str] = Query(None, description="Free-text description of the goods"),
    hs_code: Optional[str] = Query(None, description="CN-8 or TARIC-10 code, if already known"),
) -> dict:
    """Render a risk assessment in SAP GTS terminology. **Simulation, not an integration.**

    CustomsIQ is not connected to any SAP system. This reshapes the result of the
    existing `/assess-risk` call into a BAPIRET2-shaped RETURN table with GTS
    functional-area and document-status vocabulary, so the domain concepts are
    recognisable. The payload is not a valid BAPI or IDoc document and no real SAP
    system would accept it — every response says so in its own HEADER.

    Same parameters and same permissions as `/assess-risk`, because it is the same
    data: `src.customsiq.risk.assess_shipment` does the work, and
    `src.customsiq.sap_gts_bridge` only renames and reshapes what it returned.
    """
    try:
        assessment = assess_shipment(
            _conn, country_of_origin, party_name, customs_value, description, hs_code
        )
    except InvalidQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    subject_reference = (
        review.reference_for_classification(description)
        if description
        else review.reference_for_duty(hs_code or "", country_of_origin, customs_value)
    )
    return sap_gts_bridge.compliance_check(assessment, party_name, subject_reference).as_payload()


@app.get("/sap-gts/legal-control/{subject_reference}", response_model=GtsDocumentResponse)
def sap_gts_legal_control(subject_reference: str) -> dict:
    """Render a subject's recorded review decisions as a block/release check log.

    **Simulation, not an integration** — see `/sap-gts/compliance-check`. Public for
    the same reason a single subject's `/review/history` is: it is that same data,
    reshaped. A reference with no decisions returns a valid document reporting
    exactly that, not a 404 — nothing was blocked, so there is nothing to release.
    """
    decisions = review.get_review_history(_conn, subject_reference=subject_reference)
    return sap_gts_bridge.legal_control_log(decisions, subject_reference).as_payload()


@app.get("/codes/{code}/history", response_model=list[HSCodeVersionResponse])
def code_history(code: str) -> list[dict]:
    """Return one CN code's version timeline, oldest first.

    404 only if the code itself is unknown. A code that exists but was seeded
    before versioning existed (e.g. the demo data) has simply never had a
    version recorded — that's an empty list, not an error, matching how
    /search, /classify and /screen already treat "no results" as HTTP 200.
    """
    try:
        get_by_code(_conn, code)
    except HSCodeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [
        {
            "code": v.code,
            "description": v.description,
            "category": v.category,
            "valid_from": v.valid_from,
            "valid_to": v.valid_to,
            "version_label": v.version_label,
        }
        for v in fetch_hs_code_history(_conn, code)
    ]


@app.get("/codes/{code}/translations", response_model=CodeTranslationsResponse)
def code_translations(code: str) -> dict:
    """Return a CN code's description in German and French, alongside the English one.

    404 only if the code itself is unknown. A code with no translations on
    record (e.g. one of the 20 mock SAMPLE_DATA entries, which predate the
    bundled EU Combined Nomenclature import) returns null for `de`/`fr` rather
    than 404 — the code exists, it just has no supplementary language data.
    """
    try:
        record = get_by_code(_conn, code)
    except HSCodeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    translations = fetch_translations(_conn, code)
    return {
        "code": code,
        "en": record.description,
        "de": translations.get("de"),
        "fr": translations.get("fr"),
    }


class Credentials(BaseModel):
    """Body of a POST /auth/register or /auth/login request."""

    username: str
    password: str


class RoleChange(BaseModel):
    """Body of a POST /auth/users/{username}/role request."""

    role: str


@app.post("/auth/register", response_model=UserResponse)
def register(body: Credentials, request: Request, response: Response) -> dict:
    """Create an account and sign it in.

    New accounts get `auth.SELF_REGISTRATION_ROLE`. That default is a demo
    affordance: a real trade-compliance system grants roles administratively
    rather than letting a signup form choose one (see the README).
    """
    try:
        user = auth.create_user(_conn, body.username, body.password)
    except InvalidQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _set_session_cookie(request, response, auth.create_session(_conn, user))
    return _user_payload(user)


@app.post("/auth/login", response_model=UserResponse)
def login(body: Credentials, request: Request, response: Response) -> dict:
    """Verify credentials and start a session."""
    try:
        user = auth.authenticate(_conn, body.username, body.password)
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    _set_session_cookie(request, response, auth.create_session(_conn, user))
    return _user_payload(user)


@app.post("/auth/logout", response_model=LogoutResponse)
def logout(request: Request, response: Response) -> dict:
    """End the current session. Safe to call when not signed in."""
    auth.logout(_conn, request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"signed_out": True}


@app.get("/auth/me", response_model=WhoAmIResponse)
def whoami(user: Optional[User] = Depends(current_user)) -> dict:
    """Return the signed-in user, or `{"user": null}`.

    Deliberately 200 rather than 401 when anonymous: the frontend calls this on
    every page load, including for visitors who never intend to sign in.
    """
    return {"user": _user_payload(user) if user else None}


@app.get("/auth/users", response_model=list[UserResponse])
def list_users(_: User = Depends(require_permission("users:manage"))) -> list[dict]:
    """List every account. Admins only."""
    return [_user_payload(u) for u in fetch_users(_conn)]


@app.post("/auth/users/{username}/role", response_model=RoleChangeResponse)
def change_role(
    username: str,
    body: RoleChange,
    _: User = Depends(require_permission("users:manage")),
) -> dict:
    """Change one account's role. Admins only."""
    if body.role not in auth.ROLE_ORDER:
        raise HTTPException(status_code=400, detail=f"role must be one of {list(auth.ROLE_ORDER)}")
    if not update_user_role(_conn, username.strip().lower(), body.role):
        raise HTTPException(status_code=404, detail=f"No user named '{username}'")
    return {"username": username.strip().lower(), "role": body.role}


class ReviewSubmission(BaseModel):
    """Body of a POST /review request.

    There is no `reviewer_name` field: the reviewer is whoever the session cookie
    says it is. It was removed rather than accepted-and-ignored, so a client can
    never believe it set the name on an audit row.
    """

    subject_type: str
    subject_reference: str
    decision: str
    comment: Optional[str] = None


@app.post("/review", response_model=ReviewResponse)
def submit_review(body: ReviewSubmission, user: Optional[User] = Depends(current_user)) -> dict:
    """Record a human reviewer's decision on a past classification, screening or duty result.

    Reuses `src.customsiq.review.submit_review`, the same function the CLI calls.
    Append-only: this never updates an existing decision, only adds a new one.

    The permission depends on *what* is being signed off, so it's checked here
    rather than by a route-level dependency: screening sign-offs need a
    compliance officer, classification and duty need an analyst.
    """
    action = f"review:{body.subject_type}"
    if action not in auth.PERMISSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"subject_type must be one of {sorted(review.VALID_SUBJECT_TYPES)}, "
            f"got {body.subject_type!r}",
        )
    require_permission(action)(user)
    assert user is not None  # require_permission raises when there is no user

    try:
        result = review.submit_review(
            _conn,
            body.subject_type,
            body.subject_reference,
            body.decision,
            user.username,
            body.comment,
            reviewer_user_id=user.id,
        )
    except InvalidQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": result.id,
        "subject_type": result.subject_type,
        "subject_reference": result.subject_reference,
        "decision": result.decision,
        "reviewer_name": result.reviewer_name,
        "comment": result.comment,
        "reviewed_at": result.reviewed_at,
        "authenticated": True,
    }


def _review_payload(decisions: list, authored: set) -> list[dict]:
    """Serialize review rows, flagging which have an authenticated author."""
    return [
        {
            "id": r.id,
            "subject_type": r.subject_type,
            "subject_reference": r.subject_reference,
            "decision": r.decision,
            "reviewer_name": r.reviewer_name,
            "comment": r.comment,
            "reviewed_at": r.reviewed_at,
            "authenticated": r.id in authored,
        }
        for r in decisions
    ]


@app.get("/review/history", response_model=list[ReviewResponse])
def review_history(
    subject_type: Optional[str] = Query(None),
    subject_reference: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user: Optional[User] = Depends(current_user),
) -> list[dict]:
    """Return recorded review decisions, most recently reviewed first.

    One result's own trail (`subject_reference` given) stays public — that is
    the four-eyes story a visitor should see on the card they just generated.
    Browsing every reviewer's activity at once is the audit log, and needs a
    signed-in account.
    """
    if subject_reference is None:
        require_permission("audit:read")(user)
    results = review.get_review_history(_conn, subject_type, subject_reference, limit)
    return _review_payload(results, review.authored_review_ids(_conn, results))


@app.get("/dashboard/stats", response_model=DashboardStatsResponse)
def dashboard_stats(user: Optional[User] = Depends(current_user)) -> dict:
    """Return aggregate stats over reference data, review activity and CN imports.

    Reuses `src.customsiq.dashboard.get_dashboard_stats`, which itself only
    composes existing `database.py` reads — this is a reporting view, not a
    new decision. No input, so nothing here can be invalid.

    Every count is public — that's the demo. The `recent_reviews` array is not:
    it carries reviewer identities and their free-text comments, so anonymous
    callers get it empty with `recent_reviews_restricted` set. The redaction
    happens here; `dashboard.py` is not involved.
    """
    stats = get_dashboard_stats(_conn)
    may_read_audit = user is not None and auth.can(user.role, "audit:read")
    visible_reviews = stats.recent_reviews if may_read_audit else []
    authored = review.authored_review_ids(_conn, visible_reviews)
    return {
        "hs_code_count": stats.hs_code_count,
        "sanctioned_entity_count": stats.sanctioned_entity_count,
        "tariff_rate_count": stats.tariff_rate_count,
        "review_total": stats.review_total,
        "review_by_decision": stats.review_by_decision,
        "review_by_subject_type": stats.review_by_subject_type,
        "recent_reviews": _review_payload(visible_reviews, authored),
        "recent_reviews_restricted": not may_read_audit,
        "import_run_count": stats.import_run_count,
        "recent_import_runs": [
            {
                "version_label": s.run.version_label,
                "source_description": s.run.source_description,
                "imported_at": s.run.imported_at,
                "row_count": s.run.row_count,
                "changed_count": s.changed_count,
                "unchanged_count": s.unchanged_count,
            }
            for s in stats.recent_import_runs
        ],
        "versioned_code_count": stats.versioned_code_count,
    }

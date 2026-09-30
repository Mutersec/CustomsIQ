"""FastAPI HTTP surface for CN code search, sanctions screening and duty calculation."""

import sqlite3
import time
from collections.abc import Callable
from pathlib import Path
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from src.customsiq import (
    admin,
    assistant,
    auth,
    google_identity,
    mailer,
    ratings,
    review,
    sap_gts_bridge,
)
from src.customsiq.api_schemas import (
    AssistantResponse,
    AuthConfigResponse,
    ClassificationResultResponse,
    CodeTranslationsResponse,
    DashboardStatsResponse,
    DutyCalculationResponse,
    ExtractionResultResponse,
    GoogleSignInResponse,
    GtsDocumentResponse,
    HealthResponse,
    HSCodeVersionResponse,
    LogoutResponse,
    OwnRatingResponse,
    RatingsResponse,
    ReviewResponse,
    RiskAssessmentResponse,
    RoleChangeResponse,
    ScreeningResultResponse,
    SearchResult,
    SignupPendingResponse,
    UserResponse,
    WhoAmIResponse,
)
from src.customsiq.cn_classifier import classify
from src.customsiq.config import settings
from src.customsiq.dashboard import get_dashboard_stats
from src.customsiq.database import (
    delete_rating,
    delete_rating_for_user,
    fetch_hs_code_history,
    fetch_translations,
    fetch_users,
    get_by_code,
    get_connection,
    get_user_by_username,
    load_bundled_cn_nomenclature,
    load_bundled_hs_supplement,
    load_bundled_sanctions,
    seed,
    set_rating_status,
    update_user_role,
)
from src.customsiq.database import delete_user as delete_user_row
from src.customsiq.document_extraction import PDF_MAGIC, extract_invoice
from src.customsiq.embargo_screener import screen_entity
from src.customsiq.exceptions import (
    AuthenticationError,
    HSCodeNotFoundError,
    InvalidQueryError,
    RateNotFoundError,
    VerificationCooldownError,
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
    # The interactive docs and the schema they read are off unless explicitly
    # enabled: every route is behind sign-in now, and a public /openapi.json
    # would still hand anyone a complete map of them.
    docs_url="/docs" if settings.enable_api_docs else None,
    redoc_url="/redoc" if settings.enable_api_docs else None,
    openapi_url="/openapi.json" if settings.enable_api_docs else None,
)

# Resolved from this module, not the working directory: the deployed process
# may be started from anywhere, and a missing directory would raise on import.
_STATIC_DIR = Path(__file__).parent / "static"
_PRIVATE_PAGES_DIR = Path(__file__).parent / "private_pages"

_conn: sqlite3.Connection = get_connection(settings.database_target)
seed(_conn)
# Adds the real EU Combined Nomenclature 2026 on top of the 20-row mock
# SAMPLE_DATA seed() just wrote — not instead of it. The bundle is committed
# to the repo (data/cn_nomenclature_2026.csv), so this needs no network
# access and survives every cold start; upsert_hs_codes is idempotent, so
# re-running this on every restart is safe and cheap (~90 ms).
load_bundled_cn_nomenclature(_conn)
# The CN bundle misses 359 whole HS headings (4014, 8541, ...); the HS-6
# supplement fills every uncovered subheading from the public-domain WCO HS
# 2022 list, so a search never finds nothing merely because a heading is absent.
load_bundled_hs_supplement(_conn)
# Same arrangement for the sanctions list: the real OFAC SDN subset goes on top
# of the 18 invented fixture rows seed() just wrote, not instead of them. Those
# 18 are what the READMEs' worked examples and the pinned tests are built on;
# these ~5,100 are what an actual screen now hits.
load_bundled_sanctions(_conn)
if settings.seed_demo_users:
    auth.seed_demo_users(_conn)

app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


#: Paths reachable without a session: the sign-in page and what it needs.
#: Everything else — the app page and every API route — requires sign-in.
_PUBLIC_PATHS = frozenset(
    {
        "/login",
        "/health",
        "/favicon.ico",
        "/auth/login",
        "/auth/register",
        "/auth/verify",
        "/auth/resend",
        "/auth/google",
        "/auth/config",
        "/auth/me",
        "/auth/logout",
    }
)
_PUBLIC_PREFIXES = ("/static/",)


def _is_public(path: str) -> bool:
    return path in _PUBLIC_PATHS or path.startswith(_PUBLIC_PREFIXES)


# Registered before add_security_headers so that one wraps this: middleware
# added later runs outermost, and the 401s and redirects issued here need the
# security headers as much as any other response.
@app.middleware("http")
async def require_sign_in(request: Request, call_next: Callable) -> Response:
    """Admit only signed-in users, except to the sign-in page and its routes.

    A browser asking for a page is redirected to /login; any other request
    (the API) gets a JSON 401. Enforced here once rather than per route, so a
    new route is private by default instead of public by omission.
    """
    if _is_public(request.url.path):
        return await call_next(request)
    user = await run_in_threadpool(auth.user_for_token, _conn, request.cookies.get(SESSION_COOKIE))
    if user is None:
        if request.method == "GET" and request.url.path == "/":
            return RedirectResponse("/login", status_code=303)
        return JSONResponse({"detail": "Sign in to use CustomsIQ."}, status_code=401)
    # Handed to the route so `current_user` need not look the session up again.
    request.state.user = user
    return await call_next(request)


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

# Length caps on the free-text query parameters. Every one of these routes
# scores its input against all ~13.7k nomenclature rows with difflib, which is
# O(n·m) in the two string lengths — so an uncapped query is a CPU amplifier a
# single anonymous GET can fire. Measured on the real corpus: a 500-character
# query cost 5.1 s (10.4 s with a translation language), where 100 characters
# costs ~1.4 s. 100 is four times the median corpus description and comfortably
# fits a typed or invoice-prefilled product description; 60 is nearly twice the
# longest real sanctioned entity name (34 characters).
MAX_TEXT_QUERY = 100
MAX_NAME_QUERY = 60


def current_user(request: Request) -> Optional[User]:
    """Resolve the signed-in user from the session cookie, or None.

    The sign-in middleware already resolved it for every private route; the
    lookup here only runs for the public ones (/auth/me, /auth/logout).
    """
    user = getattr(request.state, "user", None)
    if user is not None:
        return user
    return auth.user_for_token(_conn, request.cookies.get(SESSION_COOKIE))


def _log(
    request: Request,
    action: str,
    detail: Optional[str] = None,
    result_count: Optional[int] = None,
    top_code: Optional[str] = None,
) -> None:
    """Record what the signed-in user just did, for the owner's activity log."""
    admin.record(
        _conn, getattr(request.state, "user", None), action, detail, result_count, top_code
    )


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


_RATE_WINDOW_SECONDS = 60.0


#: Request timestamps per client IP, for the two limits below. Same in-memory,
#: per-process shape as _UPLOAD_HITS — and the same ceiling applies.
_IP_HITS: dict = {}


def _client_ip(request: Request) -> str:
    """Best-effort client address for rate limiting.

    Behind Render's proxy `request.client.host` is the proxy, which would put
    every visitor in one bucket, so the forwarded chain wins when present.

    # ponytail: the leftmost X-Forwarded-For entry is client-settable, so an
    # attacker who rotates that header defeats this. It is kept anyway because
    # the threat it answers — a scripted password spray from one host — does
    # not rotate headers, and throttling that is worth more than the bypass
    # costs. Rate limiting at the edge (Cloudflare/Render) is the real control
    # and is a dashboard action, not something this code can do.
    """
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client else "unknown"


def _check_ip_rate_limit(request: Request, bucket: str, limit: int, what: str) -> None:
    """Allow `limit` requests per minute per client IP for `bucket`, or raise 429.

    Keyed on IP rather than account because the routes that need it most are
    pre-auth by definition: a login attempt has no authenticated principal to
    key on, which is exactly why the existing per-account limiter could not be
    reused for them.
    """
    key = (bucket, _client_ip(request))
    now = time.monotonic()
    recent = [hit for hit in _IP_HITS.get(key, []) if now - hit < _RATE_WINDOW_SECONDS]
    if len(recent) >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Too many {what}. The limit is {limit} per minute.",
        )
    recent.append(now)
    _IP_HITS[key] = recent


def _check_auth_rate_limit(request: Request) -> None:
    """Throttle the unauthenticated auth routes (findings #2, #6, #7)."""
    _check_ip_rate_limit(
        request, "auth", settings.auth_rate_limit_per_minute, "authentication attempts"
    )


def _check_search_rate_limit(request: Request) -> None:
    """Throttle the anonymous endpoints that scan the whole nomenclature.

    Each of these is a linear pass over 13.7k records; the length caps on their
    query parameters bound the cost of one request, and this bounds how many of
    them a single client can ask for.
    """
    _check_ip_rate_limit(request, "search", settings.search_rate_limit_per_minute, "requests")


@app.get("/", response_class=FileResponse, include_in_schema=False)
def index() -> FileResponse:
    """Serve the single-page web frontend.

    An explicit route rather than mounting StaticFiles at "/", which would be
    greedy enough to shadow /docs and the API routes.
    """
    return FileResponse(_STATIC_DIR / "index.html")


@app.get("/favicon.ico", response_class=FileResponse, include_in_schema=False)
def favicon() -> FileResponse:
    """The site icon at the conventional root path.

    Search engines and some browsers request /favicon.ico directly instead of
    reading the page's <link rel="icon">; without this route Google Search
    showed a generic globe next to the site. Public, like /static/*.
    """
    return FileResponse(_STATIC_DIR / "favicon.ico", media_type="image/x-icon")


@app.get("/login", response_class=FileResponse, include_in_schema=False)
def login_page() -> FileResponse:
    """Serve the dedicated sign-in page, separate from the main app."""
    return FileResponse(_STATIC_DIR / "login.html")


@app.get("/health", response_model=HealthResponse)
def health() -> dict:
    """Liveness check and basic service info.

    Public, for uptime checks. `docs` is empty unless the API docs are enabled,
    so it never advertises a route that answers 404.
    """
    docs = "/docs" if settings.enable_api_docs else ""
    return {"service": "CustomsIQ API", "docs": docs, "status": "running"}


@app.get(
    "/search", response_model=list[SearchResult], dependencies=[Depends(_check_search_rate_limit)]
)
def search_hs_codes(
    request: Request,
    q: str = Query(..., max_length=MAX_TEXT_QUERY, description="Free-text product description"),
    limit: int = Query(5, ge=1, le=50),
    language: Optional[str] = Query(
        None, description="Also match against this language's bundled descriptions, e.g. 'de'"
    ),
) -> list[dict]:
    """Return the HS codes whose description best matches `q`.

    Reuses `src.customsiq.search.search`, the same function the CLI calls,
    which is itself a thin adapter over `classify()`: `/search` and
    `/classify` rank with one engine and return the same codes and scores,
    differing only in response shape.
    """
    try:
        results = search(_conn, q, limit=limit, language=language)
    except InvalidQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _log(request, "search", q, len(results), results[0].hs_code.code if results else None)
    return [
        {
            "code": r.hs_code.code,
            "description": r.hs_code.description,
            "hierarchy_path": r.hierarchy_path,
            "category": r.hs_code.category,
            "score": r.score,
            "alias": r.alias,
        }
        for r in results
    ]


@app.get(
    "/classify",
    response_model=list[ClassificationResultResponse],
    dependencies=[Depends(_check_search_rate_limit)],
)
def classify_description(
    request: Request,
    description: str = Query(
        ..., max_length=MAX_TEXT_QUERY, description="Free-text description of the goods"
    ),
    top_n: int = Query(5, ge=1, le=50),
    language: Optional[str] = Query(
        None, description="Also match against this language's bundled descriptions, e.g. 'de'"
    ),
) -> list[dict]:
    """Suggest the CN codes a description most likely belongs to, with reasoning.

    The same engine and ranking as `/search`; this route additionally reports
    which terms drove each suggestion and a subject reference for review.
    """
    try:
        results = classify(_conn, description, top_n=top_n, language=language)
    except InvalidQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _log(
        request,
        "classify",
        description,
        len(results),
        results[0].hs_code.code if results else None,
    )
    return [
        {
            "code": r.hs_code.code,
            "description": r.hs_code.description,
            "hierarchy_path": r.hierarchy_path,
            "category": r.hs_code.category,
            "score": r.score,
            "matched_terms": r.matched_terms,
            "alias": r.alias,
            "subject_reference": review.reference_for_classification(description),
        }
        for r in results
    ]


@app.get(
    "/screen",
    response_model=list[ScreeningResultResponse],
    dependencies=[Depends(_check_search_rate_limit)],
)
def screen_name(
    request: Request,
    name: str = Query(
        ..., max_length=MAX_NAME_QUERY, description="Person or organisation name to screen"
    ),
) -> list[dict]:
    """Return every sanctioned entity that `name` may refer to.

    Reuses `src.customsiq.embargo_screener.screen_entity`, the same function
    the CLI calls, so screening logic is defined in exactly one place.
    """
    try:
        matches = screen_entity(_conn, name)
    except InvalidQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _log(request, "screen", name, len(matches))
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
    request: Request,
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
        _log(request, "duty", f"{hs_code} · {country_of_origin} · {customs_value:g}", 0)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _log(
        request,
        "duty",
        f"{hs_code} · {country_of_origin} · {customs_value:g}",
        1,
        result.hs_code,
    )
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


@app.get(
    "/assess-risk",
    response_model=RiskAssessmentResponse,
    dependencies=[Depends(_check_search_rate_limit)],
)
def assess_risk(
    request: Request,
    country_of_origin: str = Query(..., description="ISO 3166-1 alpha-2 origin code"),
    party_name: str = Query(
        ..., max_length=MAX_NAME_QUERY, description="Person or organisation to screen"
    ),
    customs_value: float = Query(..., description="Declared customs value"),
    description: Optional[str] = Query(
        None, max_length=MAX_TEXT_QUERY, description="Free-text description of the goods"
    ),
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
    _log(
        request,
        "risk",
        " · ".join(
            part for part in (party_name, country_of_origin, description or hs_code) if part
        ),
        None,
        result.hs_code,
    )
    return {
        "level": result.level,
        "composite_score": result.composite_score,
        "override": result.override,
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

    # How many fields were found, never what they say: invoices carry names,
    # addresses and prices that have no business in a log.
    await run_in_threadpool(
        admin.record,
        _conn,
        user,
        "invoice",
        f"{result.page_count} page(s)",
        len(result.fields),
    )

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


@app.get(
    "/sap-gts/compliance-check",
    response_model=GtsDocumentResponse,
    dependencies=[Depends(_check_search_rate_limit)],
)
def sap_gts_compliance_check(
    country_of_origin: str = Query(..., description="ISO 3166-1 alpha-2 origin code"),
    party_name: str = Query(
        ..., max_length=MAX_NAME_QUERY, description="Person or organisation to screen"
    ),
    customs_value: float = Query(..., description="Declared customs value"),
    description: Optional[str] = Query(
        None, max_length=MAX_TEXT_QUERY, description="Free-text description of the goods"
    ),
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
def sap_gts_legal_control(
    subject_reference: str,
    _user: User = Depends(require_permission("audit:read")),
) -> dict:
    """Render a subject's recorded review decisions as a block/release check log.

    **Simulation, not an integration** — see `/sap-gts/compliance-check`.

    Requires `audit:read`. This was public, on the reasoning that it is the
    same data as a single subject's `/review/history`, reshaped — but the
    reshaping is the problem: reviewer names, timestamps and free-text comments
    are rendered *into* the `MESSAGE` and `MESSAGE_V1..V4` fields, so the
    redaction that protects the identity fields on `/review/history` has nothing
    to act on here. Unlike that route there is no public four-eyes story to
    preserve either — this is a simulation of an internal enterprise control
    log, and its whole payload is the audit narrative. Gating it is the honest
    treatment; redacting it would leave an empty shell.

    A reference with no decisions returns a valid document reporting exactly
    that, not a 404 — nothing was blocked, so there is nothing to release.
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
    """Body of a POST /auth/login request. `username` may also be a verified e-mail."""

    username: str
    password: str


class RoleChange(BaseModel):
    """Body of a POST /auth/users/{username}/role request."""

    role: str


class SignupRequest(BaseModel):
    """Body of POST /auth/register."""

    username: str
    email: str
    password: str
    language: str = "en"


class VerifyRequest(BaseModel):
    """Body of POST /auth/verify."""

    email: str
    code: str


class ResendRequest(BaseModel):
    """Body of POST /auth/resend."""

    email: str


class GoogleRequest(BaseModel):
    """Body of POST /auth/google: the ID token Google's button returned."""

    credential: str
    # Accepted for compatibility with older sign-in pages; Google sign-in no
    # longer sends mail, so nothing is localized server-side.
    language: str = "en"


def _signup_errors(exc: Exception) -> HTTPException:
    """Map a sign-up failure to the HTTP status a client can act on."""
    if isinstance(exc, VerificationCooldownError):
        return HTTPException(
            status_code=429, detail=str(exc), headers={"Retry-After": str(exc.retry_after)}
        )
    if isinstance(exc, mailer.MailNotConfiguredError):
        return HTTPException(
            status_code=503, detail="E-mail verification is not configured on this server."
        )
    if isinstance(exc, mailer.MailDeliveryError):
        return HTTPException(status_code=502, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


_SIGNUP_FAILURES = (
    InvalidQueryError,
    AuthenticationError,
    VerificationCooldownError,
    mailer.MailNotConfiguredError,
    mailer.MailDeliveryError,
)


@app.post(
    "/auth/register",
    response_model=SignupPendingResponse,
    status_code=202,
    dependencies=[Depends(_check_auth_rate_limit)],
)
def register(body: SignupRequest) -> dict:
    """Start a sign-up: a six-digit code is e-mailed to `email`.

    No account exists yet; POST the code to /auth/verify to create it. New
    accounts get `auth.SELF_REGISTRATION_ROLE`, a demo affordance — a real
    trade-compliance system grants roles administratively (see the README).
    """
    try:
        email = auth.start_signup(_conn, body.username, body.email, body.password, body.language)
    except _SIGNUP_FAILURES as exc:
        raise _signup_errors(exc) from exc
    return {"pending": True, "email": email}


@app.post(
    "/auth/verify", response_model=UserResponse, dependencies=[Depends(_check_auth_rate_limit)]
)
def verify_signup(body: VerifyRequest, request: Request, response: Response) -> dict:
    """Confirm a sign-up with its e-mailed code, create the account, sign it in."""
    try:
        user = auth.confirm_signup(_conn, body.email, body.code)
    except _SIGNUP_FAILURES as exc:
        raise _signup_errors(exc) from exc
    admin.record(_conn, user, "signup")
    _set_session_cookie(request, response, auth.create_session(_conn, user))
    return _user_payload(user)


@app.post(
    "/auth/resend",
    response_model=SignupPendingResponse,
    dependencies=[Depends(_check_auth_rate_limit)],
)
def resend_signup_code(body: ResendRequest) -> dict:
    """E-mail a new code for a sign-up still waiting to be confirmed."""
    try:
        auth.resend_code(_conn, body.email)
    except _SIGNUP_FAILURES as exc:
        raise _signup_errors(exc) from exc
    return {"pending": True, "email": auth.normalize_email(body.email)}


@app.get("/auth/config", response_model=AuthConfigResponse)
def auth_config() -> dict:
    """Tell the sign-in page whether to show "Sign in with Google", and with what ID.

    The client ID is public by design — Google's button needs it in the page.
    """
    return {"google_client_id": settings.google_client_id}


@app.post(
    "/auth/google",
    response_model=GoogleSignInResponse,
    dependencies=[Depends(_check_auth_rate_limit)],
)
def google_sign_in(body: GoogleRequest, request: Request, response: Response) -> dict:
    """Sign in with Google, creating the account on first use.

    An existing account (by Google id, or by the same verified e-mail) is signed
    in; a new one is created on the spot. No e-mailed code: the verified token
    already proves Google checked the address.
    """
    if not settings.google_client_id:
        raise HTTPException(status_code=404, detail="Google sign-in is not enabled.")
    try:
        identity = google_identity.verify_credential(body.credential, settings.google_client_id)
        user = auth.google_sign_in(_conn, identity)
    except _SIGNUP_FAILURES as exc:
        raise _signup_errors(exc) from exc
    admin.record(_conn, user, "google")
    _set_session_cookie(request, response, auth.create_session(_conn, user))
    return {"status": "signed_in", "user": _user_payload(user), "email": identity.email}


@app.post(
    "/auth/login", response_model=UserResponse, dependencies=[Depends(_check_auth_rate_limit)]
)
def login(body: Credentials, request: Request, response: Response) -> dict:
    """Verify credentials and start a session."""
    try:
        user = auth.authenticate(_conn, body.username, body.password)
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    admin.record(_conn, user, "login")
    _set_session_cookie(request, response, auth.create_session(_conn, user))
    return _user_payload(user)


@app.post("/auth/logout", response_model=LogoutResponse)
def logout(request: Request, response: Response) -> dict:
    """End the current session. Safe to call when not signed in."""
    admin.record(_conn, current_user(request), "logout")
    auth.logout(_conn, request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"signed_out": True}


@app.get("/auth/me", response_model=WhoAmIResponse)
def whoami(user: Optional[User] = Depends(current_user)) -> dict:
    """Return the signed-in user, or `{"user": null}`.

    Deliberately 200 rather than 401 when anonymous: the frontend calls this on
    every page load, including for visitors who never intend to sign in.
    `is_owner` only decides whether the page shows the admin link; the admin
    routes check ownership again themselves.
    """
    return {"user": _user_payload(user) if user else None, "is_owner": admin.is_owner(_conn, user)}


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


class AssistantRequest(BaseModel):
    """Body of POST /assistant."""

    message: str = Field(..., min_length=1, max_length=assistant.MAX_MESSAGE)
    mode: Literal["ask", "support"] = "ask"
    language: str = "en"
    context: dict = Field(default_factory=dict)


@app.post(
    "/assistant",
    response_model=AssistantResponse,
    dependencies=[Depends(_check_search_rate_limit)],
)
def ask_assistant(body: AssistantRequest, request: Request) -> dict:
    """The rule-based assistant: a cost/code question ("ask") or a help-desk one ("support").

    No language model: `assistant.py` takes the message apart with word lists and
    patterns and answers with the same classification and duty functions the
    rest of the API uses. Free to run, and it never invents a rate.
    """
    if body.mode == "support":
        reply = assistant.support_answer(body.message, body.language)
        _log(request, "assistant", f"[support] {body.message}", int(reply["matched"]))
        return reply
    reply = assistant.answer(_conn, body.message, body.context, body.language)
    result = reply.get("result") or {}
    candidates = result.get("candidates") or result.get("matches") or []
    _log(
        request,
        "assistant",
        body.message,
        len(candidates) if result else None,
        result.get("code"),
    )
    return reply


class RatingSubmission(BaseModel):
    """Body of POST /ratings: stars and a comment about the service."""

    rating: int = Field(..., ge=1, le=5)
    comment: str = Field(..., min_length=ratings.MIN_COMMENT, max_length=ratings.MAX_COMMENT)
    company: Optional[str] = Field(None, max_length=ratings.MAX_COMPANY)


def _require_user(user: Optional[User] = Depends(current_user)) -> User:
    """The signed-in user (the sign-in middleware has already turned everyone else away)."""
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to use CustomsIQ.")
    return user


@app.get("/ratings", response_model=RatingsResponse)
def list_ratings(user: User = Depends(_require_user)) -> dict:
    """Approved ratings with their average and distribution, and the caller's own rating."""
    return ratings.overview(_conn, user)


@app.post(
    "/ratings",
    response_model=OwnRatingResponse,
    dependencies=[Depends(_check_search_rate_limit)],
)
def submit_rating(body: RatingSubmission, request: Request) -> dict:
    """Save the caller's rating. It is published only after the site owner approves it."""
    user = _require_user(getattr(request.state, "user", None))
    if len(body.comment.strip()) < ratings.MIN_COMMENT:
        raise HTTPException(
            status_code=422,
            detail=f"The comment must be at least {ratings.MIN_COMMENT} characters.",
        )
    saved = ratings.submit(_conn, user, body.rating, body.comment, body.company)
    _log(request, "rating", f"{body.rating}★ {body.comment}", body.rating)
    return saved


@app.delete("/ratings/mine")
def delete_my_rating(user: User = Depends(_require_user)) -> dict:
    """Withdraw the caller's own rating."""
    return {"deleted": delete_rating_for_user(_conn, user.id)}


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
    admin.record(
        _conn, user, "review", f"{body.subject_type}: {body.decision} · {body.subject_reference}"
    )
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


def _review_payload(decisions: list, authored: set, redact_identity: bool = False) -> list[dict]:
    """Serialize review rows, flagging which have an authenticated author.

    With `redact_identity`, the reviewer's name and free-text comment are
    withheld while the decision itself is kept. That is the split a caller
    without `audit:read` gets: the four-eyes outcome is the useful, public part
    of a result's trail; who signed it off and what they wrote about it is not.
    `/dashboard/stats` already draws the line in the same place.
    """
    return [
        {
            "id": r.id,
            "subject_type": r.subject_type,
            "subject_reference": r.subject_reference,
            "decision": r.decision,
            "reviewer_name": None if redact_identity else r.reviewer_name,
            "comment": None if redact_identity else r.comment,
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

    What a visitor sees of that trail is the decision, not the reviewer. The
    route used to return `reviewer_name` and the free-text `comment` to anyone
    who passed a `subject_reference`, which a security audit called in: the
    reference is not a secret — `/search`, `/classify`, `/screen` and
    `/calculate-duty` hand it out with every result — and `/dashboard/stats`
    already withholds exactly those two fields from anonymous callers. Two
    routes cannot hold opposite policies on one field, so identity is now
    redacted here too, while the public four-eyes story the route exists for
    survives intact.
    """
    if subject_reference is None:
        require_permission("audit:read")(user)
    may_read_identity = user is not None and auth.can(user.role, "audit:read")
    results = review.get_review_history(_conn, subject_type, subject_reference, limit)
    return _review_payload(
        results,
        review.authored_review_ids(_conn, results),
        redact_identity=not may_read_identity,
    )


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


# ---------------------------------------------------------------------------
# The site owner's admin panel
#
# Everything under /admin answers 404 to anyone who is not an owner (see
# `admin.is_owner`) — signed in or not, admin role or not — so the panel's
# existence is not even confirmed to them. Anonymous callers never get this far:
# the sign-in middleware stops them first.
# ---------------------------------------------------------------------------


def require_owner(user: Optional[User] = Depends(current_user)) -> User:
    """Admit only the site owner; everyone else sees a plain 404."""
    if user is None or not admin.is_owner(_conn, user):
        raise HTTPException(status_code=404, detail="Not Found")
    return user


@app.get("/admin", response_class=FileResponse, include_in_schema=False)
def admin_page(_: User = Depends(require_owner)) -> FileResponse:
    """Serve the owner's admin panel.

    Kept outside the public /static/ mount on purpose: from there anyone could
    fetch the page (though not the data behind it) and learn the panel exists.
    """
    return FileResponse(_PRIVATE_PAGES_DIR / "admin.html", headers={"Cache-Control": "no-store"})


@app.get("/admin/api/overview", include_in_schema=False)
def admin_overview(_: User = Depends(require_owner)) -> dict:
    """Headline numbers and system status."""
    return admin.overview(_conn, app.version)


@app.get("/admin/api/users", include_in_schema=False)
def admin_users(_: User = Depends(require_owner)) -> list[dict]:
    """Every account, newest first, with e-mail, sign-up method and last activity."""
    return admin.list_users(_conn)


def _owner_target(owner: User, username: str) -> User:
    """Resolve the account an admin action is aimed at; the owner may not target themselves."""
    target = get_user_by_username(_conn, username.strip().lower())
    if target is None:
        raise HTTPException(status_code=404, detail=f"No user named '{username}'")
    if target.id == owner.id:
        raise HTTPException(status_code=400, detail="You cannot change your own account here.")
    return target


@app.post("/admin/api/users/{username}/role", include_in_schema=False)
def admin_change_role(
    username: str, body: RoleChange, owner: User = Depends(require_owner)
) -> dict:
    """Change one account's role."""
    if body.role not in auth.ROLE_ORDER:
        raise HTTPException(status_code=400, detail=f"role must be one of {list(auth.ROLE_ORDER)}")
    target = _owner_target(owner, username)
    update_user_role(_conn, target.username, body.role)
    return {"username": target.username, "role": body.role}


@app.delete("/admin/api/users/{username}", include_in_schema=False)
def admin_delete_user(username: str, owner: User = Depends(require_owner)) -> dict:
    """Delete an account with its sessions and e-mail; its reviews and activity stay."""
    target = _owner_target(owner, username)
    delete_user_row(_conn, target.id)
    return {"deleted": target.username}


@app.get("/admin/api/activity", include_in_schema=False)
def admin_activity(
    user: Optional[str] = Query(None, max_length=64),
    action: Optional[str] = Query(None, max_length=32),
    q: Optional[str] = Query(None, max_length=MAX_TEXT_QUERY),
    zero: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: User = Depends(require_owner),
) -> dict:
    """One filtered page of the activity log, newest first."""
    return admin.activity_page(_conn, user, action, q, zero, limit, offset)


@app.get("/admin/api/searches/unmatched", include_in_schema=False)
def admin_unmatched(
    limit: int = Query(100, ge=1, le=500), _: User = Depends(require_owner)
) -> list[dict]:
    """Searches that found nothing, most frequent first."""
    return admin.unmatched_searches(_conn, limit)


class RatingStatusChange(BaseModel):
    """Body of POST /admin/api/ratings/{id}/status."""

    status: Literal["pending", "approved", "rejected"]


@app.get("/admin/api/ratings", include_in_schema=False)
def admin_ratings(
    status: Optional[Literal["pending", "approved", "rejected"]] = Query(None),
    _: User = Depends(require_owner),
) -> list[dict]:
    """Every rating (or those of one status), most recently updated first."""
    return ratings.for_owner(_conn, status)


@app.post("/admin/api/ratings/{rating_id}/status", include_in_schema=False)
def admin_rating_status(
    rating_id: int, body: RatingStatusChange, _: User = Depends(require_owner)
) -> dict:
    """Approve, reject, or send a rating back to pending."""
    if not set_rating_status(_conn, rating_id, body.status):
        raise HTTPException(status_code=404, detail="No such rating.")
    return {"id": rating_id, "status": body.status}


@app.delete("/admin/api/ratings/{rating_id}", include_in_schema=False)
def admin_delete_rating(rating_id: int, _: User = Depends(require_owner)) -> dict:
    """Delete a rating outright."""
    if not delete_rating(_conn, rating_id):
        raise HTTPException(status_code=404, detail="No such rating.")
    return {"deleted": rating_id}

"""Read a commercial invoice PDF and pull out the fields the existing forms need.

A convenience layer, not a decision engine. Nothing here classifies, prices or
scores anything: it turns a PDF into strings and numbers, and the user reviews
them before pressing the buttons that call `cn_classifier`, `tariff_calculator`
and `risk` exactly as they always have. This module deliberately imports none of
those seven modules — a test enforces that, so it can't quietly become a second
decision engine.

Scope, stated plainly rather than sold around: this reads PDFs that have a **text
layer** and label their fields one per line ("Country of Origin: NO"). It does not
do OCR — a scanned page is detected and reported as such, never silently returned
as an empty result — and it will miss values laid out in borderless table columns,
split across two columns, or written in prose. Partial extraction is the expected
case, which is why `missing` and `completeness` are part of the result.
"""

import logging
import re
from dataclasses import dataclass
from io import BytesIO
from typing import Optional

from src.customsiq.exceptions import InvalidQueryError
from src.utils.validators import validate_cn_code, validate_country_code

logger = logging.getLogger(__name__)

#: Every PDF begins with this. Checked against the bytes themselves, never the
#: filename or a declared content type.
PDF_MAGIC = b"%PDF-"

#: Only the first pages are read. An invoice's fields are on page one; the cap
#: stops a thousand-page upload from spending the instance's CPU.
MAX_PAGES = 10

_MISSING_DRIVER = (
    "PDF support needs 'pip install -r requirements.txt' (pypdf). "
    "Invoice extraction is unavailable without it."
)

#: The fields we look for, each mapped onto an argument an existing function
#: already takes. Labels are matched case-insensitively; the longest matching
#: label on a line wins, so "Commodity Code" resolves to hs_code rather than
#: description's shorter "Commodity".
FIELD_LABELS = {
    "hs_code": (
        "HS Code",
        "HS-Code",
        "Commodity Code",
        "Tariff Code",
        "Customs Code",
        "CN Code",
        "Taric Code",
    ),
    "customs_value": (
        "Total Invoice Value",
        "Invoice Value",
        "Customs Value",
        "Total Value",
        "Total Amount",
        "Invoice Total",
        "Total",
        "Amount",
        "Value",
    ),
    "country_of_origin": (
        "Country of Origin",
        "Origin Country",
        "Made In",
        "Origin",
    ),
    "party_name": (
        "Consignee",
        "Consignee Name",
        "Supplier",
        "Exporter",
        "Seller",
        "Shipper",
    ),
    "description": (
        "Description of Goods",
        "Goods Description",
        "Product Description",
        "Description",
        "Commodity",
        "Product",
        "Goods",
    ),
}

#: Which label wins when a document carries several for the same field. Only
#: party_name needs it: denied-party screening is about the counterparty, so a
#: Consignee line beats the Exporter line above it regardless of page order.
_LABEL_PREFERENCE = {"party_name": FIELD_LABELS["party_name"]}

_CURRENCY_SYMBOLS = {"€": "EUR", "$": "USD", "£": "GBP", "₺": "TRY"}
_CURRENCY_CODES = frozenset(
    {"EUR", "USD", "GBP", "CHF", "NOK", "SEK", "DKK", "PLN", "TRY", "JPY", "CNY", "CAD"}
)

#: Country names accepted in place of an ISO code. Deliberately short: the trade
#: partners in this project's seed data plus the EU/EEA. A name outside it comes
#: back raw with a note, for the user to correct in the form — inventing a
#: 250-entry gazetteer here would be data this project has no source for.
_COUNTRY_NAMES = {
    "austria": "AT",
    "belarus": "BY",
    "belgium": "BE",
    "bulgaria": "BG",
    "canada": "CA",
    "china": "CN",
    "croatia": "HR",
    "cyprus": "CY",
    "czechia": "CZ",
    "czech republic": "CZ",
    "denmark": "DK",
    "estonia": "EE",
    "finland": "FI",
    "france": "FR",
    "germany": "DE",
    "greece": "GR",
    "hungary": "HU",
    "ireland": "IE",
    "italy": "IT",
    "japan": "JP",
    "kazakhstan": "KZ",
    "latvia": "LV",
    "liberia": "LR",
    "lithuania": "LT",
    "luxembourg": "LU",
    "malta": "MT",
    "netherlands": "NL",
    "north macedonia": "MK",
    "norway": "NO",
    "panama": "PA",
    "poland": "PL",
    "portugal": "PT",
    "romania": "RO",
    "serbia": "RS",
    "singapore": "SG",
    "slovakia": "SK",
    "slovenia": "SI",
    "spain": "ES",
    "sweden": "SE",
    "switzerland": "CH",
    "turkey": "TR",
    "türkiye": "TR",
    "united arab emirates": "AE",
    "united kingdom": "GB",
    "united states": "US",
    "usa": "US",
}

# Labels paired with their field, longest first so the most specific one on a
# line wins. Built once at import.
_LABEL_INDEX = sorted(
    ((label, field) for field, labels in FIELD_LABELS.items() for label in labels),
    key=lambda pair: len(pair[0]),
    reverse=True,
)

# "<label> : <value>" — the separator may be a colon, a dash or an en dash.
_LINE_PATTERN = re.compile(
    r"^\s*(" + "|".join(re.escape(label) for label, _ in _LABEL_INDEX) + r")\s*[:\-–]\s*(.+)$",
    re.IGNORECASE,
)

_LABEL_TO_FIELD = {label.lower(): field for label, field in _LABEL_INDEX}

# A number with optional thousands/decimal separators, e.g. 12,450.00 or 1.234,56.
_NUMBER_PATTERN = re.compile(r"\d[\d.,\s]*\d|\d")


@dataclass(frozen=True)
class ExtractedField:
    """One field found in a document, with the evidence for it.

    Attributes:
        name: Which field this is, e.g. "country_of_origin".
        value: The usable value, normalized where this project has a validator
            for it (ISO country code, digits-only HS code, float-ready amount).
        label: The label text on the document that produced it, so a reviewer
            can see *why* this value was picked — the same explainability
            contract as `classify`'s matched_terms and `risk`'s factors.
        source_line: The line exactly as it appeared in the document.
    """

    name: str
    value: str
    label: str
    source_line: str


@dataclass(frozen=True)
class ExtractionResult:
    """Everything one upload produced, including what it failed to find.

    Attributes:
        fields: The fields that were found.
        missing: Names of the fields that were not, so a partial extraction
            reports itself instead of looking like a parse failure.
        page_count: How many pages were read (capped at MAX_PAGES).
        has_text_layer: False for a scanned/image PDF, where OCR would be needed.
        notes: Human-readable caveats, e.g. an unrecognised country name.
    """

    fields: list
    missing: list
    page_count: int
    has_text_layer: bool
    notes: list

    @property
    def completeness(self) -> float:
        """Share of known fields that were found, 0.0–1.0."""
        total = len(FIELD_LABELS) + 1  # + currency, which rides along with the value
        return round(len(self.fields) / total, 2)

    def value_of(self, name: str) -> Optional[str]:
        """Return one field's value, or None if it wasn't found."""
        for field in self.fields:
            if field.name == name:
                return field.value
        return None


def _normalize_hs_code(raw: str) -> Optional[str]:
    """Strip grouping characters and keep it only if it's a real CN/TARIC code.

    Invoices group these several ways — "6109100000", "6109 10 0000",
    "6109.10.0000" — so the leading run of digits and separators is taken as a
    whole (a trailing "6109100000 Cotton T-shirts" stops at the word), then
    validated by the project's own `validate_cn_code`.
    """
    leading = re.match(r"^[\d\s.\-]+", raw)
    candidate = re.sub(r"[\s.\-]", "", leading.group(0)) if leading else ""
    return candidate if validate_cn_code(candidate) else None


def _normalize_country(raw: str) -> tuple:
    """Return (value, note). An alpha-2 code passes through; a known name maps."""
    cleaned = raw.strip().strip(".,")
    if validate_country_code(cleaned):
        return cleaned.upper(), None
    mapped = _COUNTRY_NAMES.get(cleaned.lower())
    if mapped:
        return mapped, None
    return cleaned, f"Country of origin {cleaned!r} isn't a recognised name or ISO code."


def _parse_amount(raw: str) -> Optional[str]:
    """Pull a number out of a value line, handling both separator conventions.

    "12,450.00" and "1.234,56" are the same amount written two ways. The rule:
    whichever separator appears *last* is the decimal point, and the other is a
    thousands separator. With only one separator present, three trailing digits
    mean thousands ("3.400" is 3400), anything else is a decimal ("3.40").
    """
    match = _NUMBER_PATTERN.search(raw)
    if not match:
        return None
    number = re.sub(r"\s", "", match.group(0))

    if "," in number and "." in number:
        decimal_sep = "," if number.rfind(",") > number.rfind(".") else "."
        number = number.replace("," if decimal_sep == "." else ".", "")
        number = number.replace(decimal_sep, ".")
    elif "," in number or "." in number:
        separator = "," if "," in number else "."
        head, _, tail = number.rpartition(separator)
        if len(tail) == 3 and separator in number[:-4] or len(tail) == 3:
            number = head.replace(separator, "") + tail
        else:
            number = head.replace(separator, "") + "." + tail

    try:
        return str(float(number))
    except ValueError:
        return None


def _parse_currency(raw: str) -> Optional[str]:
    """Find an ISO currency code or a common symbol on the amount's line."""
    for symbol, code in _CURRENCY_SYMBOLS.items():
        if symbol in raw:
            return code
    for token in re.findall(r"[A-Za-z]{3}", raw):
        if token.upper() in _CURRENCY_CODES:
            return token.upper()
    return None


def extract_fields(text: str) -> ExtractionResult:
    """Pull labelled fields out of already-extracted document text.

    Pure: no file access, no network, no database. Most of this module's tests
    drive it directly with a string, no PDF involved.

    Args:
        text: The document's text, one field per line.

    Returns:
        An ExtractionResult listing what was found, what wasn't, and why.
    """
    candidates: dict = {}
    notes: list = []
    currency: Optional[ExtractedField] = None

    for line in text.splitlines():
        match = _LINE_PATTERN.match(line)
        if not match:
            continue
        label, raw_value = match.group(1), match.group(2).strip()
        field_name = _LABEL_TO_FIELD[label.lower()]
        if not raw_value:
            continue

        if field_name == "hs_code":
            code_value = _normalize_hs_code(raw_value)
            if code_value is None:
                notes.append(f"Ignored {label!r}: {raw_value!r} isn't a valid CN/TARIC code.")
                continue
            value = code_value
        elif field_name == "country_of_origin":
            value, note = _normalize_country(raw_value)
            if note:
                notes.append(note)
        elif field_name == "customs_value":
            amount = _parse_amount(raw_value)
            if amount is None:
                notes.append(f"Ignored {label!r}: no amount found in {raw_value!r}.")
                continue
            value = amount
            code = _parse_currency(raw_value)
            if code and currency is None:
                currency = ExtractedField("currency", code, label, line.rstrip())
        else:
            value = raw_value

        found = ExtractedField(field_name, value, label, line.rstrip())
        candidates.setdefault(field_name, []).append(found)

    fields = [_pick(name, found) for name, found in candidates.items()]
    if currency is not None:
        fields.append(currency)

    found_names = {field.name for field in fields}
    missing = [name for name in FIELD_LABELS if name not in found_names]
    if "currency" not in found_names:
        missing.append("currency")

    return ExtractionResult(
        fields=sorted(fields, key=lambda f: f.name),
        missing=sorted(missing),
        page_count=0,
        has_text_layer=bool(text.strip()),
        notes=notes,
    )


def _pick(name: str, found: list) -> ExtractedField:
    """Choose between several matches for one field.

    Document order wins, except where a preference is declared: an invoice names
    both an Exporter and a Consignee, and screening cares about the Consignee
    whichever came first on the page.
    """
    preference = _LABEL_PREFERENCE.get(name)
    if preference is None:
        return found[0]
    ranked = {label.lower(): index for index, label in enumerate(preference)}
    return min(found, key=lambda f: ranked.get(f.label.lower(), len(ranked)))


def extract_text(data: bytes) -> tuple:
    """Extract the text layer from a PDF held in memory.

    The bytes stay in a BytesIO for the life of the call: nothing is written to
    disk, here or anywhere else in this module.

    Args:
        data: The raw PDF bytes.

    Returns:
        (text, page_count) — text is empty for a scanned document.

    Raises:
        InvalidQueryError: If the bytes aren't a PDF, are encrypted, or are
            malformed. Encrypted files are refused rather than prompted for.
        RuntimeError: If pypdf isn't installed.
    """
    if not data.startswith(PDF_MAGIC):
        raise InvalidQueryError("That file isn't a PDF.")

    try:
        import pypdf
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise RuntimeError(_MISSING_DRIVER) from exc

    try:
        reader = pypdf.PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise InvalidQueryError("Encrypted PDFs aren't supported. Remove the password first.")
        pages = reader.pages[:MAX_PAGES]
        text = "\n".join(page.extract_text() or "" for page in pages)
    except InvalidQueryError:
        raise
    except Exception as exc:  # pypdf raises a variety of parse errors
        logger.info("could not parse uploaded PDF: %s", type(exc).__name__)
        raise InvalidQueryError("That PDF could not be read — it may be damaged.") from exc

    return text, len(pages)


def extract_invoice(data: bytes) -> ExtractionResult:
    """Read a PDF and return the invoice fields found in it.

    Args:
        data: The raw PDF bytes.

    Returns:
        An ExtractionResult. A scanned PDF comes back with `has_text_layer`
        False and a note saying so, rather than an empty field list that would
        look like a parser bug.

    Raises:
        InvalidQueryError: If the PDF can't be read (see `extract_text`).
    """
    text, page_count = extract_text(data)
    result = extract_fields(text)
    notes = list(result.notes)
    if not result.has_text_layer:
        notes.append(
            "This PDF has no text layer — it looks like a scan. Optical character "
            "recognition isn't available on this deployment."
        )
    return ExtractionResult(
        fields=result.fields,
        missing=result.missing,
        page_count=page_count,
        has_text_layer=result.has_text_layer,
        notes=notes,
    )

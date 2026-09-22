"""Regenerate the sample invoice PDFs used by tests/test_document_extraction.py.

Committed so the binary fixtures next to it are reproducible and reviewable — a
.pdf in a repo is otherwise a black box. Run it from the repo root:

    python tests/fixtures/make_invoice_pdfs.py

It writes minimal, uncompressed PDF syntax by hand rather than pulling in a
PDF-*writing* dependency: pypdf is a reader, and a text-layer page is only a few
hundred bytes of `BT ... Tj ... ET`. That also makes the fixtures diffable.
"""

from pathlib import Path

FIXTURES = Path(__file__).parent

# A realistic labelled invoice: every field the extractor knows about is present,
# and the consignee is a name the seeded sanctions list actually matches, so the
# same fixture drives the end-to-end risk walkthrough in the README.
SAMPLE_INVOICE_LINES = [
    "COMMERCIAL INVOICE                         Invoice No: INV-2026-0417",
    "                                           Date: 2026-03-14",
    "",
    "Exporter:  Solvia Textiles AS, Oslo",
    "Consignee: Northwind Maritime Holdings Ltd, Limassol",
    "",
    "Description of Goods: Cotton T-shirts, knitted",
    "HS Code:              6109100000",
    "Country of Origin:    Norway",
    "Invoice Value:        EUR 12,450.00",
    "",
    "Terms: CIF Limassol. Payment within 30 days.",
]

# Same document minus the fields an incomplete invoice tends to omit, for the
# missing-field path.
PARTIAL_INVOICE_LINES = [
    "COMMERCIAL INVOICE",
    "",
    "Description: Portable computers, laptops",
    "Total Amount: USD 3400.00",
    "",
    "Delivery: DAP Rotterdam",
]


def _escape(text: str) -> str:
    """Escape the three characters that are special inside a PDF string."""
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _content_stream(lines: list) -> bytes:
    """One text-showing operator per line, top-down on an A4 page."""
    parts = ["BT", "/F1 11 Tf", "13 TL", "1 0 0 1 40 780 Tm"]
    for line in lines:
        parts.append(f"({_escape(line)}) Tj" if line else "()Tj")
        parts.append("T*")
    parts.append("ET")
    return "\n".join(parts).encode("latin-1")


def build_pdf(lines: list) -> bytes:
    """Assemble a one-page PDF. An empty `lines` gives a page with no text layer."""
    content = _content_stream(lines) if lines else b""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n".encode()
    out += b"%%EOF\n"
    return bytes(out)


def main() -> None:
    written = {
        "sample_invoice.pdf": build_pdf(SAMPLE_INVOICE_LINES),
        "partial_invoice.pdf": build_pdf(PARTIAL_INVOICE_LINES),
        # A page with no text operators at all: what a scanned document looks
        # like to a text extractor, without shipping an actual scan.
        "scanned_invoice.pdf": build_pdf([]),
    }
    for name, data in written.items():
        (FIXTURES / name).write_bytes(data)
        print(f"wrote {name} ({len(data)} bytes)")


if __name__ == "__main__":
    main()

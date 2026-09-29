"""Build data/hs2022_supplement.csv: the HS-6 subheadings the EU CN bundle lacks.

Why this exists: the committed EU Combined Nomenclature bundle
(data/cn_nomenclature_2026.csv) turned out to cover only 870 of the 1,229 HS
headings and 2,716 of the 5,613 HS-6 subheadings. Whole headings are missing:
4014 (sheath contraceptives), 8541 (photovoltaic panels) and hundreds more.
The EU source files needed to rebuild it are not reachable from where this
was done, so the gap is closed one level up instead, from the international
Harmonized System itself.

Source: data/hs2022_source.csv, the WCO Harmonized System 2022 nomenclature
as published by the `datasets/harmonized-system` project (data from UN
Comtrade), licence ODC-PDDL-1.0 (public domain). It is committed unchanged,
so this build is reproducible offline:

    python scripts/build_hs_supplement.py

For every HS-6 subheading that no bundled CN code starts with, one row is
written:

- `hs_code`      the six-digit HS code itself. Deliberately *not* padded to
                 eight digits: "40141000" would be an invented CN code, while
                 "401410" is exactly what the source says.
- `category`     the same chapter -> category mapping the CN import uses.
- `description_en`  the subheading text.
- `context_en`   the heading (HS-4) text, so results carry a hierarchy path.

English only: the source has no German or French text. When the full EU
source files are available, rebuild the CN bundle instead; its CN-8/TARIC-10
codes then cover these subheadings and this supplement shrinks accordingly.
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.import_cn_codes import category_for_code  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"
SOURCE = DATA / "hs2022_source.csv"
BUNDLE = DATA / "cn_nomenclature_2026.csv"
OUTPUT = DATA / "hs2022_supplement.csv"

FIELDS = ("hs_code", "category", "description_en", "context_en")


def build_rows(source_rows: list, bundled_codes: set) -> list:
    """The supplement rows, in HS order, for subheadings the bundle does not cover.

    Args:
        source_rows: Rows of the HS source CSV (section, hscode, description,
            parent, level).
        bundled_codes: Every code in the EU CN bundle.

    Returns:
        One dict per missing HS-6 subheading, keyed by FIELDS.
    """
    covered = {code[:6] for code in bundled_codes}
    headings = {row["hscode"]: row["description"] for row in source_rows if row["level"] == "4"}
    rows = []
    for row in source_rows:
        code = row["hscode"]
        if row["level"] != "6" or code in covered:
            continue
        rows.append(
            {
                "hs_code": code,
                "category": category_for_code(code),
                "description_en": row["description"].strip(),
                "context_en": headings.get(code[:4], "").strip(),
            }
        )
    return rows


def main() -> None:
    with SOURCE.open(newline="", encoding="utf-8") as handle:
        source_rows = list(csv.DictReader(handle))
    with BUNDLE.open(newline="", encoding="utf-8") as handle:
        bundled = {row["cn_code"] for row in csv.DictReader(handle)}

    rows = build_rows(source_rows, bundled)
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} HS-6 subheadings to {OUTPUT}")


if __name__ == "__main__":
    main()

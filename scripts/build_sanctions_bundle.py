"""Build the committed sanctions bundle from OFAC's published SDN List.

Run once, offline, by hand — never by the application. The output is what gets
committed to the repo and loaded at every startup (see
`database.load_bundled_sanctions`), the same "process once, commit the result"
pattern `scripts/import_cn_codes.py build-bundle` already uses for the CN
nomenclature and `tests/fixtures/make_invoice_pdfs.py` for the invoice PDFs.

    curl -L -o sdn.csv https://www.treasury.gov/ofac/downloads/sdn.csv
    curl -L -o add.csv https://www.treasury.gov/ofac/downloads/add.csv
    python scripts/build_sanctions_bundle.py sdn.csv add.csv \
        --snapshot-date 2026-09-22 --output data/sanctions_ofac_2026.csv

**Why OFAC and not an aggregator.** The SDN List is a work of the United States
Government and is therefore in the public domain under 17 U.S.C. § 105: no
licence to accept, no non-commercial restriction, nothing to attribute beyond
naming the source honestly. The obvious alternative, OpenSanctions' consolidated
export, is published under CC-BY-**NC** 4.0, and OpenSanctions' own guidance says
"Compliance screening is a commercial use even though it generates no revenue",
which a publicly deployed screening demo cannot cleanly satisfy. OFAC is also
simply the more authoritative choice: it is one of the lists a real trade-
compliance tool screens against, not a third party's reading of it.

**The source files carry no header row.** OFAC's own tutorial says so: "the
column names are not stored in the actual sanctions list data files". The layouts
below are transcribed from OFAC's published data specification
(https://www.treasury.gov/ofac/downloads/consolidated/cons_dat_spec.txt).
"""

import argparse
import collections
import csv
import logging
import re
import sys
from pathlib import Path
from typing import NamedTuple, Optional

# Running this file directly puts scripts/ on sys.path, not the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.customsiq.logging_config import configure_logging

logger = logging.getLogger(__name__)

#: OFAC's null marker. It is written with a trailing space in the real files.
NULL_MARKER = "-0-"

#: SDN.CSV's record layout, from OFAC's data specification.
SDN_COLUMNS = (
    "ent_num",
    "name",
    "sdn_type",
    "program",
    "title",
    "call_sign",
    "vess_type",
    "tonnage",
    "grt",
    "vess_flag",
    "vess_owner",
    "remarks",
)

#: ADD.CSV's record layout. `ent_num` links back to SDN.CSV's primary key.
ADD_COLUMNS = ("ent_num", "add_num", "address", "city", "country", "add_remarks")

#: The programmes this bundle keeps, by prefix. A customs and export-control
#: tool exists for embargo and dual-use regimes, so those are what it screens
#: against: the Russia/Ukraine, Iran, DPRK, Belarus and Syria programmes, plus
#: non-proliferation (NPWMD), the Iranian financial and IRGC designations, and
#: CAATSA. Matched by prefix because OFAC versions them by executive order
#: (RUSSIA-EO14024, IRAN-EO13902, DPRK4, …) and a new EO should be picked up
#: without editing this list.
PROGRAMME_PREFIXES = (
    "RUSSIA",
    "UKRAINE",
    "IRAN",
    "DPRK",
    "BELARUS",
    "SYRIA",
    "NPWMD",
    "IFSR",
    "IRGC",
    "CAATSA",
)

#: Entities kept per programme. Not a size limit — the whole 19,391-entry list
#: would be about 2 MB, comfortably smaller than the 3.1 MB CN bundle already
#: committed. It is a *latency* limit: `embargo_screener.screen_entity`
#: deliberately takes no `limit`, because silently truncating a hit list would
#: be a compliance failure, so every entity is scored on every screen at a
#: measured ~70 µs each. 600 lands the deduplicated total near 5,100 entities
#: and screening near 360 ms, which is the envelope `search()` already occupies
#: against the 13.7k-row nomenclature.
PROGRAMME_CAP = 600

#: Placeholder for an entity OFAC lists without any usable country. ISO 3166-1
#: reserves ZZ for exactly this. It is a real answer, not a guess: OFAC routinely
#: publishes an individual with an empty address row and no nationality.
UNKNOWN_COUNTRY = "ZZ"

LIST_NAME = "US OFAC SDN"

#: OFAC's country spellings mapped to ISO 3166-1 alpha-2, which is what
#: `sanctioned_entities.country` is documented to hold. Hand-written rather than
#: pulled from a dependency, for the reason the README's authentication section
#: already gives for rejecting passlib: this project keeps its runtime on the
#: standard library, and a 200-entry literal is cheaper than a package.
#:
#: Keys are matched case-insensitively with whitespace collapsed, which is what
#: absorbs the real file's inconsistencies — "PANAMA" beside "Panama", four
#: spellings of St Kitts, two of Sao Tome. Vessel flags are folded in here too:
#: they use their own spellings ("Democratic People's Republic of Korea" where
#: an address says "Korea, North").
COUNTRY_ISO2: dict[str, str] = {
    "afghanistan": "AF",
    "albania": "AL",
    "algeria": "DZ",
    "angola": "AO",
    "antigua & barbuda": "AG",
    "antigua and barbuda": "AG",
    "argentina": "AR",
    "armenia": "AM",
    "aruba": "AW",
    "australia": "AU",
    "austria": "AT",
    "azerbaijan": "AZ",
    "bahamas, the": "BS",
    "bahrain": "BH",
    "bangladesh": "BD",
    "barbados": "BB",
    "belarus": "BY",
    "belgium": "BE",
    "belize": "BZ",
    "benin": "BJ",
    "bermuda": "BM",
    "bolivia": "BO",
    "bosnia and herzegovina": "BA",
    "botswana": "BW",
    # OFAC's own data-quality artefact: the address is Botswana, flagged as a
    # false document. The country of the address is still Botswana.
    "botswana false": "BW",
    "brazil": "BR",
    "british virgin islands": "VG",
    "bulgaria": "BG",
    "burkina faso": "BF",
    "burma": "MM",
    "cambodia": "KH",
    "cameroon": "CM",
    "canada": "CA",
    "cayman islands": "KY",
    "central african republic": "CF",
    "chile": "CL",
    "china": "CN",
    "colombia": "CO",
    "comoros": "KM",
    "congo, democratic republic of the": "CD",
    "congo, republic of the": "CG",
    "cook islands": "CK",
    "costa rica": "CR",
    "cote d ivoire": "CI",
    "croatia": "HR",
    "cuba": "CU",
    "curacao": "CW",
    "cyprus": "CY",
    "czech republic": "CZ",
    "democratic people's republic of korea": "KP",
    "denmark": "DK",
    "djibouti": "DJ",
    "dominica": "DM",
    "dominican republic": "DO",
    "ecuador": "EC",
    "egypt": "EG",
    "el salvador": "SV",
    "equatorial guinea": "GQ",
    "eritrea": "ER",
    "estonia": "EE",
    "eswatini": "SZ",
    "ethiopia": "ET",
    "finland": "FI",
    "france": "FR",
    "gabon": "GA",
    "gambia": "GM",
    "georgia": "GE",
    "germany": "DE",
    "ghana": "GH",
    "gibraltar": "GI",
    "greece": "GR",
    "guatemala": "GT",
    "guernsey": "GG",
    "guinea": "GN",
    "guyana": "GY",
    "haiti": "HT",
    "honduras": "HN",
    "hong kong": "HK",
    "hungary": "HU",
    "iceland": "IS",
    "india": "IN",
    "indonesia": "ID",
    "iran": "IR",
    "iraq": "IQ",
    "ireland": "IE",
    "israel": "IL",
    "italy": "IT",
    "jamaica": "JM",
    "japan": "JP",
    "jersey": "JE",
    "jordan": "JO",
    "kazakhstan": "KZ",
    "kenya": "KE",
    "kiribati": "KI",
    "korea, north": "KP",
    "korea, south": "KR",
    "kosovo": "XK",  # user-assigned; Kosovo has no ISO 3166-1 code of its own
    "kuwait": "KW",
    "kyrgyzstan": "KG",
    "laos": "LA",
    "latvia": "LV",
    "lebanon": "LB",
    "liberia": "LR",
    "libya": "LY",
    "liechtenstein": "LI",
    "lithuania": "LT",
    "luxembourg": "LU",
    "macau": "MO",
    "malaysia": "MY",
    "maldives": "MV",
    "mali": "ML",
    "malta": "MT",
    "man, isle of": "IM",
    "marshall islands": "MH",
    "mauritania": "MR",
    "mauritius": "MU",
    "mexico": "MX",
    "moldova": "MD",
    "monaco": "MC",
    "mongolia": "MN",
    "montenegro": "ME",
    "morocco": "MA",
    "mozambique": "MZ",
    "mozambique (false)": "MZ",  # same artefact as "Botswana False"
    "namibia": "NA",
    "netherlands": "NL",
    "new zealand": "NZ",
    "nicaragua": "NI",
    "niger": "NE",
    "nigeria": "NG",
    "north macedonia, the republic of": "MK",
    "norway": "NO",
    "oman": "OM",
    "pakistan": "PK",
    "palau": "PW",
    "palestinian": "PS",
    "panama": "PA",
    "paraguay": "PY",
    "peru": "PE",
    "philippines": "PH",
    "poland": "PL",
    "portugal": "PT",
    "qatar": "QA",
    "republic of palau": "PW",
    "romania": "RO",
    "russia": "RU",
    "rwanda": "RW",
    "saint kitts and nevis": "KN",
    "saint vincent and the grenadines": "VC",
    "samoa": "WS",
    "san marino": "SM",
    "sao tome & principe": "ST",
    "sao tome and principe": "ST",
    "saudi arabia": "SA",
    "senegal": "SN",
    "serbia": "RS",
    "seychelles": "SC",
    "sierra leone": "SL",
    "singapore": "SG",
    "sint maarten": "SX",
    "slovakia": "SK",
    "slovenia": "SI",
    "somalia": "SO",
    "south africa": "ZA",
    "south sudan": "SS",
    "spain": "ES",
    "sri lanka": "LK",
    "st kitts & nevis": "KN",
    "st. kitts & nevis": "KN",
    "st. kitts and nevis": "KN",
    "st. vincent and grenadines": "VC",
    "st. vincent and the grenadines": "VC",
    "sudan": "SD",
    "suriname": "SR",
    "sweden": "SE",
    "switzerland": "CH",
    "syria": "SY",
    "taiwan": "TW",
    "tajikistan": "TJ",
    "tanzania": "TZ",
    "thailand": "TH",
    "the gambia": "GM",
    "togo": "TG",
    "trinidad and tobago": "TT",
    "tunisia": "TN",
    "turkey": "TR",
    "turkmenistan": "TM",
    "tuvalu": "TV",
    "uganda": "UG",
    "ukraine": "UA",
    "united arab emirates": "AE",
    "united kingdom": "GB",
    "united states": "US",
    "uruguay": "UY",
    "uzbekistan": "UZ",
    "vanuatu": "VU",
    "venezuela": "VE",
    "vietnam": "VN",
    "virgin islands, british": "VG",
    "west bank": "PS",
    "yemen": "YE",
    "zambia": "ZM",
    "zimbabwe": "ZW",
    # OFAC's explicit "we don't know" values.
    "none identified": UNKNOWN_COUNTRY,
    "unknown": UNKNOWN_COUNTRY,
    # Regions. Mapped only where ISO 3166 itself puts the territory inside one
    # country, so this stays a lookup and not a political claim: Crimea is part
    # of ISO 3166-2:UA, Gaza and the West Bank are ISO 3166-1 PS, northern Mali
    # is ML. Where ISO splits the territory between states, or where the region
    # is not a territory at all, the honest answer is ZZ rather than a pick.
    "region: crimea": "UA",
    "region: gaza": "PS",
    "region: north gaza": "PS",
    "region: northern gaza": "PS",
    "region: west bank": "PS",
    "region: northern mali": "ML",
    "region: iran": "IR",
    "region: russia": "RU",
    "region: jammu and kashmir": UNKNOWN_COUNTRY,
    "region: kashmir": UNKNOWN_COUNTRY,
    "region: kafia kingi": UNKNOWN_COUNTRY,
    "region: commonwealth of independent states": UNKNOWN_COUNTRY,
}


class BundleError(Exception):
    """Raised when the OFAC source files cannot be mapped as expected."""


class SdnEntity(NamedTuple):
    """One primary SDN record, with the fields this bundle maps."""

    ent_num: int
    name: str
    sdn_type: str
    programmes: tuple[str, ...]
    vessel_flag: str


class BundleRow(NamedTuple):
    """One row of the committed bundle."""

    name: str
    country: str
    list_source: str
    date_added: str


def clean_field(value: Optional[str]) -> str:
    """Strip OFAC's `-0-` null marker and surrounding whitespace."""
    text = (value or "").strip()
    return "" if text == NULL_MARKER else text


def is_blank_row(row: list[str]) -> bool:
    """Return whether a CSV row carries no data at all.

    OFAC's files end with a lone DOS end-of-file character (0x1A), which
    `csv.reader` hands over as a one-field row `['\x1a']`. Plain `.strip()`
    leaves it, so it has to be named explicitly or every build logs a spurious
    "short row" warning on the last line.
    """
    return not any(field.strip().strip("\x1a").strip() for field in row)


def split_programmes(field: str) -> tuple[str, ...]:
    """Split SDN.CSV's `Program` column into individual programme codes.

    OFAC packs several programmes into the one column as `A] [B] [C`, i.e. the
    separator is the bracket pair between them and the outermost brackets are
    absent. Anything else — a single code, or an empty field — falls through
    unchanged.

    Args:
        field: The raw `Program` value.

    Returns:
        The programme codes, in the order given.
    """
    joined = field.replace("] [", "\x00").strip("[]")
    return tuple(code.strip() for code in joined.split("\x00") if code.strip())


def iso2_for(country_name: str) -> str:
    """Map one of OFAC's country spellings to an ISO 3166-1 alpha-2 code.

    Args:
        country_name: The raw string, from an address or a vessel flag.

    Returns:
        The two-letter code, or `UNKNOWN_COUNTRY` for an empty input.

    Raises:
        BundleError: If the name is non-empty and not in `COUNTRY_ISO2`. This
            fails the build rather than quietly emitting ZZ: a spelling OFAC
            has added since this dict was written is something to look at, not
            something to bury.
    """
    normalised = re.sub(r"\s+", " ", country_name).strip().lower()
    if not normalised:
        return UNKNOWN_COUNTRY
    try:
        return COUNTRY_ISO2[normalised]
    except KeyError as exc:
        raise BundleError(
            f"No ISO 3166-1 alpha-2 code for OFAC country {country_name!r}. "
            f"Add it to COUNTRY_ISO2 in {Path(__file__).name}."
        ) from exc


def country_for(entity: SdnEntity, addresses: list[dict]) -> str:
    """Decide one country for an entity that may have several, or none.

    The first address by `add_num` wins — OFAC's own ordering, and the closest
    thing the file has to a primary address. A vessel with no usable address
    falls back to its flag, which is the country that actually matters for a
    ship. Everything else is ZZ.

    Args:
        entity: The primary SDN record.
        addresses: Its ADD.CSV rows, in any order.

    Returns:
        An ISO 3166-1 alpha-2 code, possibly `UNKNOWN_COUNTRY`.
    """
    for address in sorted(addresses, key=lambda row: int(row["add_num"])):
        if address["country"]:
            return iso2_for(address["country"])
    if entity.vessel_flag:
        return iso2_for(entity.vessel_flag)
    return UNKNOWN_COUNTRY


def is_in_scope(programmes: tuple[str, ...]) -> tuple[str, ...]:
    """Return the entity's programmes that this bundle covers."""
    return tuple(code for code in programmes if code.startswith(PROGRAMME_PREFIXES))


def select_entities(
    entities: list[SdnEntity], cap: int = PROGRAMME_CAP
) -> tuple[list[SdnEntity], collections.Counter]:
    """Pick the bundled subset: in-scope programmes, capped per programme.

    Deterministic and reproducible. Entities are considered in `ent_num` order,
    which is OFAC's own designation order — oldest listings first, so the
    long-standing designations a reader is most likely to recognise are the ones
    that survive the cap. An entity is kept when *any* of its in-scope
    programmes still has room, and it then counts against all of them, so no
    programme is silently dropped the way a plain "first N rows of the file"
    would drop everything after the Russia block.

    Args:
        entities: Every primary SDN record.
        cap: Maximum entities counted per programme.

    Returns:
        The selected entities in `ent_num` order, and the per-programme tally.
    """
    used: collections.Counter = collections.Counter()
    selected = []
    for entity in sorted(entities, key=lambda item: item.ent_num):
        scoped = is_in_scope(entity.programmes)
        if not scoped:
            continue
        if any(used[code] < cap for code in scoped):
            selected.append(entity)
            for code in scoped:
                used[code] += 1
    return selected, used


def build_rows(
    entities: list[SdnEntity], addresses: dict, snapshot_date: str
) -> tuple[list[BundleRow], int]:
    """Map selected entities onto the bundle's four columns.

    `sanctioned_entities.name` is a PRIMARY KEY, so a name OFAC lists twice —
    the same vessel under two designations, say — can only appear once. The
    first occurrence in `ent_num` order wins and the rest are counted.

    Args:
        entities: The selected entities, in `ent_num` order.
        addresses: {ent_num: [ADD.CSV rows]}.
        snapshot_date: The list's publication date, ISO 8601.

    Returns:
        The bundle rows, and how many duplicate names were collapsed.
    """
    rows: dict[str, BundleRow] = {}
    collapsed = 0
    for entity in entities:
        if entity.name in rows:
            collapsed += 1
            continue
        programmes = "/".join(is_in_scope(entity.programmes))
        rows[entity.name] = BundleRow(
            name=entity.name,
            country=country_for(entity, addresses.get(str(entity.ent_num), [])),
            list_source=f"{LIST_NAME} — {programmes}",
            date_added=snapshot_date,
        )
    return list(rows.values()), collapsed


def read_sdn(path: Path) -> list[SdnEntity]:
    """Read SDN.CSV into primary records. Headerless — see the module docstring."""
    entities = []
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        for line_number, row in enumerate(csv.reader(handle), start=1):
            if is_blank_row(row):
                continue
            if len(row) < len(SDN_COLUMNS):
                logger.warning("%s line %d: short row, skipping", path.name, line_number)
                continue
            fields = dict(zip(SDN_COLUMNS, [clean_field(value) for value in row]))
            if not fields["name"] or not fields["ent_num"].isdigit():
                logger.warning("%s line %d: unusable row, skipping", path.name, line_number)
                continue
            entities.append(
                SdnEntity(
                    ent_num=int(fields["ent_num"]),
                    name=fields["name"],
                    sdn_type=fields["sdn_type"] or "entity",
                    programmes=split_programmes(fields["program"]),
                    vessel_flag=fields["vess_flag"],
                )
            )
    if not entities:
        raise BundleError(f"{path} yielded no SDN records — is it really OFAC's SDN.CSV?")
    return entities


def read_addresses(path: Path) -> dict:
    """Read ADD.CSV into {ent_num: [rows]}. Headerless, linked by `ent_num`."""
    addresses: dict = collections.defaultdict(list)
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        for row in csv.reader(handle):
            if len(row) < len(ADD_COLUMNS):
                continue
            fields = dict(zip(ADD_COLUMNS, [clean_field(value) for value in row]))
            if fields["ent_num"].isdigit() and fields["add_num"].isdigit():
                addresses[fields["ent_num"]].append(fields)
    return addresses


def build_bundle(
    sdn_path: Path,
    add_path: Path,
    output_path: Path,
    snapshot_date: str,
    cap: int = PROGRAMME_CAP,
) -> int:
    """Write the committed bundle CSV, and log what went into it.

    Args:
        sdn_path: OFAC's SDN.CSV.
        add_path: OFAC's ADD.CSV.
        output_path: Where to write the bundle.
        snapshot_date: The list's publication date, ISO 8601.
        cap: Entities counted per programme.

    Returns:
        The number of rows written.
    """
    entities = read_sdn(sdn_path)
    addresses = read_addresses(add_path)
    selected, tally = select_entities(entities, cap)
    rows, collapsed = build_rows(selected, addresses, snapshot_date)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["name", "country", "list_source", "date_added"])
        for row in sorted(rows, key=lambda item: item.name):
            writer.writerow([row.name, row.country, row.list_source, row.date_added])

    unknown = sum(1 for row in rows if row.country == UNKNOWN_COUNTRY)
    logger.info(
        "read %d SDN records, selected %d, wrote %d rows to %s "
        "(%d duplicate names collapsed, %d with country %s)",
        len(entities),
        len(selected),
        len(rows),
        output_path,
        collapsed,
        unknown,
        UNKNOWN_COUNTRY,
    )
    # Per-programme counts of *bundled* entities, which can exceed `cap`: an
    # entity kept because one of its programmes had room still counts against
    # every programme it carries. That is the point — an entity is in the bundle
    # or it is not, and it does not stop belonging to a full programme.
    logger.info("bundled entities per programme:")
    for code, count in tally.most_common():
        logger.info("  %-24s %5d", code, count)
    return len(rows)


def main(argv: Optional[list[str]] = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("sdn", type=Path, help="OFAC SDN.CSV")
    parser.add_argument("add", type=Path, help="OFAC ADD.CSV")
    parser.add_argument(
        "--snapshot-date",
        required=True,
        help="Publication date of the downloaded list, ISO 8601 (e.g. 2026-09-22)",
    )
    parser.add_argument("--output", type=Path, required=True, help="Output CSV path")
    parser.add_argument("--cap", type=int, default=PROGRAMME_CAP, help="Entities per programme")
    args = parser.parse_args(argv)

    configure_logging()
    try:
        build_bundle(args.sdn, args.add, args.output, args.snapshot_date, args.cap)
    except (BundleError, FileNotFoundError) as exc:
        logger.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

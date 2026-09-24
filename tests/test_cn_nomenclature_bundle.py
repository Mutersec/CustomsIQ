"""Tests for loading the bundled EU Combined Nomenclature into a running database.

The bundle itself (data/cn_nomenclature_2026.csv) is spot-checked against the
real export in tests/test_import_cn_codes.py::TestBundledNomenclature. These
tests cover the loading path: upsert_translations, fetch_translations, and
load_bundled_cn_nomenclature — using a small synthetic CSV so they don't
depend on, or re-verify, the full 13,733-row bundle.
"""

import csv
import sqlite3
from pathlib import Path

import pytest

from src.customsiq.database import (
    SAMPLE_DATA,
    fetch_all,
    fetch_translations,
    get_connection,
    load_bundled_cn_nomenclature,
    seed,
    upsert_translations,
)


@pytest.fixture
def conn() -> sqlite3.Connection:
    """An in-memory database, seeded like the other modules' tests."""
    connection = get_connection(":memory:")
    seed(connection)
    return connection


@pytest.fixture
def tiny_bundle(tmp_path: Path) -> Path:
    """A 2-row bundle CSV in the real format, for fast/isolated loading tests."""
    path = tmp_path / "cn_bundle.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["cn_code", "category", "description_en", "description_de", "description_fr"]
        )
        writer.writerow(
            [
                "01012910",
                "Animal Products",
                "For slaughter",
                "zum Schlachten",
                "destinés à la boucherie",
            ]
        )
        writer.writerow(
            [
                "94033000",
                "Furniture",
                "Wooden office furniture",
                "Büromöbel aus Holz",
                "Meubles de bureau en bois",
            ]
        )
    return path


class TestUpsertAndFetchTranslations:
    """The plain read/write accessors, independent of the bundle format."""

    def test_a_translation_round_trips(self, conn: sqlite3.Connection) -> None:
        upsert_translations(conn, [("01012910", "de", "zum Schlachten")])
        assert fetch_translations(conn, "01012910") == {"de": "zum Schlachten"}

    def test_multiple_languages_for_one_code(self, conn: sqlite3.Connection) -> None:
        upsert_translations(
            conn,
            [("01012910", "de", "zum Schlachten"), ("01012910", "fr", "destinés à la boucherie")],
        )
        assert fetch_translations(conn, "01012910") == {
            "de": "zum Schlachten",
            "fr": "destinés à la boucherie",
        }

    def test_a_code_with_no_translations_returns_empty(self, conn: sqlite3.Connection) -> None:
        assert fetch_translations(conn, "6109100000") == {}

    def test_upserting_again_updates_rather_than_duplicates(self, conn: sqlite3.Connection) -> None:
        upsert_translations(conn, [("01012910", "de", "old text")])
        upsert_translations(conn, [("01012910", "de", "new text")])
        assert fetch_translations(conn, "01012910") == {"de": "new text"}


class TestLoadBundledCnNomenclature:
    """The startup-time loading path api.py calls on every cold start."""

    def test_loads_codes_and_translations(
        self, conn: sqlite3.Connection, tiny_bundle: Path
    ) -> None:
        count = load_bundled_cn_nomenclature(conn, tiny_bundle)
        assert count == 2
        assert fetch_translations(conn, "01012910") == {
            "de": "zum Schlachten",
            "fr": "destinés à la boucherie",
        }

    def test_the_english_description_lands_in_hs_codes(
        self, conn: sqlite3.Connection, tiny_bundle: Path
    ) -> None:
        load_bundled_cn_nomenclature(conn, tiny_bundle)
        record = next(r for r in fetch_all(conn) if r.code == "01012910")
        assert record.description == "For slaughter"
        assert record.category == "Animal Products"

    def test_sample_data_is_untouched_and_supplemented_not_replaced(
        self, conn: sqlite3.Connection, tiny_bundle: Path
    ) -> None:
        """The mock demo rows stay exactly as seed() put them."""
        load_bundled_cn_nomenclature(conn, tiny_bundle)
        codes = {r.code for r in fetch_all(conn)}
        assert {record.code for record in SAMPLE_DATA} <= codes
        assert len(codes) == len(SAMPLE_DATA) + 2

    def test_is_idempotent_on_repeat_calls(
        self, conn: sqlite3.Connection, tiny_bundle: Path
    ) -> None:
        load_bundled_cn_nomenclature(conn, tiny_bundle)
        load_bundled_cn_nomenclature(conn, tiny_bundle)
        codes = [r.code for r in fetch_all(conn)]
        assert len(codes) == len(set(codes))  # no duplicates
        assert len(codes) == len(SAMPLE_DATA) + 2

    def test_a_changed_bundle_updates_in_place_on_the_next_load(
        self, conn: sqlite3.Connection, tiny_bundle: Path
    ) -> None:
        """Re-running against an updated bundle (e.g. next year's CN) must not
        require deleting the old data first — upsert, not seed-once."""
        load_bundled_cn_nomenclature(conn, tiny_bundle)

        with tiny_bundle.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                ["cn_code", "category", "description_en", "description_de", "description_fr"]
            )
            writer.writerow(
                ["01012910", "Animal Products", "Updated text", "Neuer Text", "Nouveau texte"]
            )

        load_bundled_cn_nomenclature(conn, tiny_bundle)
        record = next(r for r in fetch_all(conn) if r.code == "01012910")
        assert record.description == "Updated text"
        assert fetch_translations(conn, "01012910")["de"] == "Neuer Text"

    def test_defaults_to_the_committed_repo_bundle(self, conn: sqlite3.Connection) -> None:
        """No path argument -> the real, committed data/cn_nomenclature_2026.csv."""
        count = load_bundled_cn_nomenclature(conn)
        assert count == 13733
        total = len(fetch_all(conn))
        assert total == len(SAMPLE_DATA) + 13733

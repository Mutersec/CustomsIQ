"""Tests for the CN reference-data import tool."""

import logging
from pathlib import Path

import pytest

from scripts.import_cn_codes import (
    PROGRESS_EVERY,
    CNImportError,
    category_for_code,
    import_file,
    main,
    normalise_code,
    parse_records,
)
from src.customsiq.database import fetch_all, get_connection

FIXTURE = Path(__file__).parent / "fixtures" / "sample_cn_codes.csv"

# The fixture holds 10 leaf codes plus 2 hierarchy rows ("61", "6109").
LEAF_CODES = 10
HIERARCHY_ROWS = 2


def write_csv(path: Path, body: str) -> Path:
    """Write a small CN-shaped CSV and return its path."""
    path.write_text("CN_CODE,DESCRIPTION_EN\n" + body, encoding="utf-8")
    return path


class TestChapterMapping:
    """Chapter (first two digits) to category mapping."""

    def test_section_categories(self) -> None:
        """Codes map to the category of their HS section."""
        assert category_for_code("61091000") == "Textile"
        assert category_for_code("72269900") == "Metals"
        assert category_for_code("09012100") == "Vegetable Products"

    def test_chapter_overrides_beat_their_section(self) -> None:
        """Chapters with their own label win over the section default."""
        assert category_for_code("85171200") == "Electronics"  # section: Machinery
        assert category_for_code("87032110") == "Automotive"  # section: Transport
        assert category_for_code("30049000") == "Pharmaceutical"  # section: Chemicals
        assert category_for_code("94033000") == "Furniture"  # section: Miscellaneous

    def test_reserved_chapter_falls_back(self) -> None:
        """Reserved (77) and national (99) chapters get the fallback category."""
        assert category_for_code("77010000") == "Other"
        assert category_for_code("99999999") == "Other"


class TestParsing:
    """Reading and classifying rows of a CN export."""

    def test_normalise_code_strips_grouping(self) -> None:
        """CN exports group digits with spaces or dots; only digits survive."""
        assert normalise_code("6109 10 00") == "61091000"
        assert normalise_code("6109.10.00") == "61091000"
        assert normalise_code("") == ""

    def test_parses_leaf_codes_from_the_fixture(self) -> None:
        """Every 8-digit leaf row becomes a record, with a derived category."""
        records, skipped, malformed = parse_records(FIXTURE)
        assert len(records) == LEAF_CODES
        assert skipped == HIERARCHY_ROWS
        assert malformed == 0

        by_code = {r.code: r for r in records}
        assert by_code["61091000"].description.startswith("T-shirts")
        assert by_code["61091000"].category == "Textile"
        assert by_code["85171200"].category == "Electronics"
        assert by_code["97050000"].category == "Art & Antiques"

    def test_hierarchy_rows_are_skipped_not_flagged(self) -> None:
        """Chapter and heading rows are expected input, not malformed."""
        _, skipped, malformed = parse_records(FIXTURE)
        assert skipped == HIERARCHY_ROWS
        assert malformed == 0

    def test_malformed_rows_are_skipped_with_a_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A bad row is logged and skipped; good rows in the same file still import."""
        csv_path = write_csv(
            tmp_path / "mixed.csv",
            "6109 10 00,Cotton T-shirts\n"
            "ABCDEFGH,Not a numeric code\n"
            "8517 12 00,\n"  # missing description
            "123,Wrong digit count\n"
            "8507 60 00,Lithium-ion accumulators\n",
        )
        with caplog.at_level(logging.WARNING):
            records, _, malformed = parse_records(csv_path)

        assert [r.code for r in records] == ["61091000", "85076000"]
        assert malformed == 3
        assert "malformed" in caplog.text

    def test_column_override(self, tmp_path: Path) -> None:
        """Unrecognised headers can be pointed at explicitly."""
        path = tmp_path / "odd.csv"
        path.write_text("weird_code,weird_text\n6109 10 00,Cotton T-shirts\n", encoding="utf-8")
        records, _, _ = parse_records(
            path, code_column="weird_code", description_column="weird_text"
        )
        assert records[0].code == "61091000"

    def test_unknown_headers_raise_a_helpful_error(self, tmp_path: Path) -> None:
        """An unrecognisable file fails loudly, naming the headers it found."""
        path = tmp_path / "bad.csv"
        path.write_text("alpha,beta\n1,2\n", encoding="utf-8")
        with pytest.raises(CNImportError, match="alpha"):
            parse_records(path)

    def test_missing_override_column_raises(self, tmp_path: Path) -> None:
        """An override naming a column that isn't there fails clearly."""
        with pytest.raises(CNImportError, match="nope"):
            parse_records(write_csv(tmp_path / "f.csv", "6109 10 00,X\n"), code_column="nope")

    def test_unsniffable_file_falls_back_to_comma(self, tmp_path: Path) -> None:
        """A file the sniffer cannot classify still parses as plain CSV."""
        path = tmp_path / "plain.csv"
        path.write_text("CN_CODE,DESCRIPTION_EN\n61091000,Cotton T-shirts\n", encoding="utf-8")
        records, _, _ = parse_records(path)
        assert records[0].code == "61091000"

    def test_empty_file_raises(self, tmp_path: Path) -> None:
        """A file with no header row fails rather than importing nothing silently."""
        path = tmp_path / "empty.csv"
        path.write_text("", encoding="utf-8")
        with pytest.raises(CNImportError, match="no header row"):
            parse_records(path)

    def test_progress_is_logged_for_large_files(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Progress is reported every PROGRESS_EVERY parsed codes."""
        body = "".join(f"8517{i:04d},Device {i}\n" for i in range(PROGRESS_EVERY))
        with caplog.at_level(logging.INFO):
            records, _, _ = parse_records(write_csv(tmp_path / "big.csv", body))
        assert len(records) == PROGRESS_EVERY
        assert f"parsed {PROGRESS_EVERY} codes" in caplog.text

    def test_semicolon_delimited_file(self, tmp_path: Path) -> None:
        """CN exports are often semicolon-separated; the dialect is sniffed."""
        path = tmp_path / "semi.csv"
        path.write_text("CN_CODE;DESCRIPTION_EN\n6109 10 00;Cotton T-shirts\n", encoding="utf-8")
        records, _, _ = parse_records(path)
        assert records[0].code == "61091000"


class TestImport:
    """Writing parsed records into the database."""

    def test_imports_into_the_hs_codes_table(self, tmp_path: Path) -> None:
        """Imported codes land in the same table the application reads."""
        db = str(tmp_path / "cn.db")
        assert import_file(FIXTURE, db) == LEAF_CODES

        conn = get_connection(db)
        stored = {r.code: r for r in fetch_all(conn)}
        conn.close()

        assert len(stored) == LEAF_CODES
        assert stored["94033000"].category == "Furniture"

    def test_reimport_is_idempotent(self, tmp_path: Path) -> None:
        """Running the import twice must not duplicate rows."""
        db = str(tmp_path / "cn.db")
        import_file(FIXTURE, db)
        import_file(FIXTURE, db)

        conn = get_connection(db)
        stored = fetch_all(conn)
        conn.close()
        assert len(stored) == LEAF_CODES

    def test_reimport_updates_changed_descriptions(self, tmp_path: Path) -> None:
        """An upsert refreshes an existing code rather than duplicating it."""
        db = str(tmp_path / "cn.db")
        import_file(write_csv(tmp_path / "v1.csv", "6109 10 00,Old wording\n"), db)
        import_file(write_csv(tmp_path / "v2.csv", "6109 10 00,New wording\n"), db)

        conn = get_connection(db)
        stored = fetch_all(conn)
        conn.close()
        assert len(stored) == 1
        assert stored[0].description == "New wording"

    def test_batching_writes_every_record(self, tmp_path: Path) -> None:
        """A batch size smaller than the file still writes all rows."""
        db = str(tmp_path / "cn.db")
        import_file(FIXTURE, db, batch_size=3)

        conn = get_connection(db)
        count = len(fetch_all(conn))
        conn.close()
        assert count == LEAF_CODES


class TestCommandLine:
    """The argparse entry point."""

    def test_main_imports_a_file(self, tmp_path: Path) -> None:
        """A successful run exits 0 and populates the given database."""
        db = str(tmp_path / "cli.db")
        assert main([str(FIXTURE), "--db", db]) == 0

        conn = get_connection(db)
        count = len(fetch_all(conn))
        conn.close()
        assert count == LEAF_CODES

    def test_main_reports_a_missing_file(self, tmp_path: Path) -> None:
        """A missing input exits 1 instead of raising a traceback."""
        assert main([str(tmp_path / "nope.csv"), "--db", str(tmp_path / "x.db")]) == 1

    def test_main_reports_an_unreadable_file(self, tmp_path: Path) -> None:
        """A file with unrecognisable headers exits 1."""
        path = tmp_path / "bad.csv"
        path.write_text("alpha,beta\n1,2\n", encoding="utf-8")
        assert main([str(path), "--db", str(tmp_path / "x.db")]) == 1

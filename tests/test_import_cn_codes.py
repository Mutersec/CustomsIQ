"""Tests for the CN reference-data import tool."""

import logging
from pathlib import Path

import pytest

from scripts.import_cn_codes import (
    PROGRESS_EVERY,
    CNImportError,
    category_for_code,
    collapse_suffix_variants,
    import_file,
    main,
    normalise_code,
    parse_records,
    select_leaf_codes,
)
from src.customsiq.database import (
    fetch_all,
    fetch_cn_import_runs,
    fetch_hs_code_history,
    get_connection,
)

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

    def test_reimport_with_changed_description_versions_history(self, tmp_path: Path) -> None:
        """A changed code closes its old history row and opens a new one."""
        db = str(tmp_path / "cn.db")
        v1 = write_csv(tmp_path / "v1.csv", "6109 10 00,Old wording\n")
        v2 = write_csv(tmp_path / "v2.csv", "6109 10 00,New wording\n")
        import_file(v1, db, version_label="CN2025")
        import_file(v2, db, version_label="CN2026")

        conn = get_connection(db)
        history = fetch_hs_code_history(conn, "61091000")
        current = {r.code: r for r in fetch_all(conn)}
        conn.close()

        assert len(history) == 2
        assert history[0].description == "Old wording"
        assert history[0].valid_to is not None  # closed, not deleted
        assert history[1].description == "New wording"
        assert history[1].valid_to is None  # current
        assert history[0].version_label == "CN2025"
        assert history[1].version_label == "CN2026"
        assert current["61091000"].description == "New wording"  # hs_codes unchanged in shape

    def test_reimport_with_unchanged_data_creates_no_spurious_version(self, tmp_path: Path) -> None:
        """Re-importing identical data must not add a new history row."""
        db = str(tmp_path / "cn.db")
        csv_path = write_csv(tmp_path / "v1.csv", "6109 10 00,Same wording\n")
        import_file(csv_path, db, version_label="CN2025")
        import_file(csv_path, db, version_label="CN2025-rerun")

        conn = get_connection(db)
        history = fetch_hs_code_history(conn, "61091000")
        conn.close()
        assert len(history) == 1

    def test_current_only_reads_unaffected_by_history(self, tmp_path: Path) -> None:
        """hs_codes never grows extra rows, however many versions a code has."""
        db = str(tmp_path / "cn.db")
        v1 = write_csv(tmp_path / "v1.csv", "6109 10 00,Old wording\n")
        v2 = write_csv(tmp_path / "v2.csv", "6109 10 00,New wording\n")
        v3 = write_csv(tmp_path / "v3.csv", "6109 10 00,Newest wording\n")
        import_file(v1, db, version_label="CN2025")
        import_file(v2, db, version_label="CN2026")
        import_file(v3, db, version_label="CN2027")

        conn = get_connection(db)
        stored = fetch_all(conn)
        conn.close()
        assert len(stored) == 1

    def test_import_run_is_logged_every_time(self, tmp_path: Path) -> None:
        """Every run is logged, even one that changes nothing."""
        db = str(tmp_path / "cn.db")
        csv_path = write_csv(tmp_path / "v1.csv", "6109 10 00,Same wording\n")
        import_file(csv_path, db, version_label="CN2025")
        import_file(csv_path, db, version_label="CN2025-rerun")

        conn = get_connection(db)
        runs = fetch_cn_import_runs(conn)
        conn.close()
        assert [r.version_label for r in runs] == ["CN2025-rerun", "CN2025"]  # newest first
        assert all(r.row_count == 1 for r in runs)


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


class TestSuffixCollapse:
    """Eurostat statistical-suffix variants collapse to one description per code."""

    def test_the_80_suffix_wins_when_present(self) -> None:
        by_code = {"01012910": {"10": "For slaughter", "80": "Other"}}
        assert collapse_suffix_variants(by_code) == {"01012910": "Other"}

    def test_a_single_variant_is_used_regardless_of_its_suffix(self) -> None:
        by_code = {"01012910": {"10": "For slaughter"}}
        assert collapse_suffix_variants(by_code) == {"01012910": "For slaughter"}

    def test_the_first_encountered_variant_wins_without_an_80(self) -> None:
        """Dict insertion order is preserved in Python, so this is deterministic."""
        by_code = {"01012910": {"10": "First", "20": "Second"}}
        assert collapse_suffix_variants(by_code) == {"01012910": "First"}

    def test_multiple_codes_are_handled_independently(self) -> None:
        by_code = {
            "01012910": {"80": "Other"},
            "01012990": {"10": "For slaughter", "80": "Other again"},
        }
        assert collapse_suffix_variants(by_code) == {
            "01012910": "Other",
            "01012990": "Other again",
        }


class TestLeafSelection:
    """A CN-8 code with TARIC-10 children isn't a declarable leaf on its own."""

    def test_a_cn8_code_with_taric10_children_is_dropped(self) -> None:
        candidates = {
            "85115000": "Other generators",  # would-be CN-8 leaf
            "8511500010": "For use in civil aircraft",  # its real leaf children
            "8511500090": "Other",
        }
        result = select_leaf_codes(candidates)
        assert "85115000" not in result
        assert result == {
            "8511500010": "For use in civil aircraft",
            "8511500090": "Other",
        }

    def test_a_cn8_code_with_no_children_is_kept(self) -> None:
        candidates = {"01012910": "For slaughter"}
        assert select_leaf_codes(candidates) == candidates

    def test_a_taric10_orphan_with_no_cn8_row_is_kept(self) -> None:
        """The hierarchy sometimes jumps straight from a 6-digit heading to
        TARIC-10 with no intervening CN-8 row — confirmed against the real
        export (e.g. 8511500000's children). Nothing to drop it in favour of."""
        candidates = {"8511500010": "For use in civil aircraft"}
        assert select_leaf_codes(candidates) == candidates

    def test_unrelated_codes_are_unaffected(self) -> None:
        candidates = {"01012910": "For slaughter", "94033000": "Wooden office furniture"}
        assert select_leaf_codes(candidates) == candidates


class TestBundledNomenclature:
    """The committed data/cn_nomenclature_2026.csv bundle, spot-checked for real."""

    BUNDLE = Path(__file__).parent.parent / "data" / "cn_nomenclature_2026.csv"

    @pytest.fixture(scope="class")
    def rows(self) -> list:
        import csv

        with self.BUNDLE.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def test_the_bundle_is_committed_and_readable(self, rows: list) -> None:
        assert self.BUNDLE.exists()
        assert len(rows) == 13733

    def test_every_code_is_a_valid_cn_or_taric_code(self, rows: list) -> None:
        from src.utils.validators import validate_cn_code

        assert all(validate_cn_code(row["cn_code"]) for row in rows)

    def test_every_row_has_all_three_languages_and_a_category(self, rows: list) -> None:
        assert all(
            row["description_en"] and row["description_de"] and row["description_fr"]
            for row in rows
        )
        assert all(row["category"] for row in rows)

    def test_codes_are_unique(self, rows: list) -> None:
        codes = [row["cn_code"] for row in rows]
        assert len(codes) == len(set(codes))

    def test_a_known_real_code_matches_its_documented_worked_example(self, rows: list) -> None:
        """The exact row shown in the README's leaf-selection example."""
        by_code = {row["cn_code"]: row for row in rows}
        assert by_code["01012910"]["description_en"] == "For slaughter"
        assert by_code["01012910"]["description_de"] == "zum Schlachten"
        assert by_code["01012910"]["category"] == "Animal Products"

    def test_a_cn8_code_with_taric10_children_does_not_appear(self, rows: list) -> None:
        """85115000 has real TARIC-10 children in the source export (verified
        by direct inspection) and must not appear itself."""
        codes = {row["cn_code"] for row in rows}
        assert "85115000" not in codes
        assert "8511500010" in codes
        assert "8511500090" in codes

    def test_none_of_sample_datas_mock_codes_collide_with_real_ones(self, rows: list) -> None:
        from src.customsiq.database import SAMPLE_DATA

        codes = {row["cn_code"] for row in rows}
        assert not codes & {record.code for record in SAMPLE_DATA}

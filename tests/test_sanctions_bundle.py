"""Tests for the real OFAC SDN bundle and the mapping that produced it.

Phase 9 deliberately kept the sanctions list fictional while the CN nomenclature
became real. This reverses that half: `data/sanctions_ofac_2026.csv` holds a real
subset of the US OFAC Specially Designated Nationals List, and the running app
screens against it.

Two halves, tested separately:

- the pure mapping in `scripts/build_sanctions_bundle.py` — OFAC's headerless
  layout, its `] [` programme packing, its `-0-` nulls, its DOS end-of-file
  byte and its 217 country spellings — tested without needing the source files,
  the same split `import_cn_codes`'s `collapse_suffix_variants` already uses; and
- the loading and screening path, including that the 18 invented fixture entities
  still behave exactly as they did, because every pinned worked example in this
  project is built on them.
"""

import csv
import sqlite3
from pathlib import Path

import pytest

from scripts.build_sanctions_bundle import (
    COUNTRY_ISO2,
    LIST_NAME,
    UNKNOWN_COUNTRY,
    BundleError,
    SdnEntity,
    build_rows,
    clean_field,
    country_for,
    is_blank_row,
    is_in_scope,
    iso2_for,
    select_entities,
    split_programmes,
)
from src.customsiq.database import (
    SANCTIONED_ENTITIES,
    fetch_all_entities,
    get_connection,
    load_bundled_sanctions,
    seed,
    upsert_entities,
)
from src.customsiq.embargo_screener import screen_entity
from src.customsiq.models import SanctionedEntity

BUNDLE = Path(__file__).parent.parent / "data" / "sanctions_ofac_2026.csv"

#: Snapshot date of the committed bundle. Every row carries it, because OFAC's
#: CSV export publishes no per-entity listing date at all — see the README.
SNAPSHOT_DATE = "2026-09-22"


def _entity(ent_num=1, name="ACME OOO", sdn_type="entity", program="RUSSIA-EO14024", flag=""):
    """An SdnEntity with only the fields the mapping reads."""
    return SdnEntity(ent_num, name, sdn_type, split_programmes(program), flag)


class TestCleanField:
    """OFAC writes its nulls as `-0-`, with a trailing space in the real files."""

    def test_the_null_marker_becomes_empty(self) -> None:
        assert clean_field("-0-") == ""
        assert clean_field("-0- ") == ""

    def test_real_values_are_stripped_but_kept(self) -> None:
        assert clean_field("  GAZPROM INVEST, OOO  ") == "GAZPROM INVEST, OOO"

    def test_missing_is_empty(self) -> None:
        assert clean_field(None) == ""

    def test_a_value_merely_containing_the_marker_survives(self) -> None:
        assert clean_field("MV -0- STAR") == "MV -0- STAR"


class TestIsBlankRow:
    """The last line of OFAC's files is a DOS end-of-file byte, not a blank."""

    def test_the_dos_eof_byte_counts_as_blank(self) -> None:
        """Without this every build logged a spurious short-row warning."""
        assert is_blank_row(["\x1a"])

    def test_an_empty_row_is_blank(self) -> None:
        assert is_blank_row([]) and is_blank_row(["", "  "])

    def test_a_row_with_data_is_not(self) -> None:
        assert not is_blank_row(["58653", "CENTRO DE INVESTIGACION"])


class TestSplitProgrammes:
    """OFAC packs several programmes into one column as `A] [B] [C`."""

    def test_a_single_programme(self) -> None:
        assert split_programmes("RUSSIA-EO14024") == ("RUSSIA-EO14024",)

    def test_several_programmes(self) -> None:
        assert split_programmes("UKRAINE-EO13662] [RUSSIA-EO14024") == (
            "UKRAINE-EO13662",
            "RUSSIA-EO14024",
        )

    def test_three_programmes_keep_their_order(self) -> None:
        assert split_programmes("IRAN] [IFSR] [IRGC") == ("IRAN", "IFSR", "IRGC")

    def test_an_empty_field_yields_nothing(self) -> None:
        assert split_programmes("") == ()

    def test_surrounding_brackets_are_not_kept(self) -> None:
        assert split_programmes("[CUBA]") == ("CUBA",)


class TestIso2For:
    """`country` is documented as ISO 3166-1 alpha-2, so it has to be one."""

    def test_a_plain_name(self) -> None:
        assert iso2_for("Russia") == "RU"

    def test_matching_ignores_case_and_extra_whitespace(self) -> None:
        """The real file has "PANAMA" next to "Panama"."""
        assert iso2_for("PANAMA") == "PA"
        assert iso2_for("  united   kingdom ") == "GB"

    def test_the_vessel_flag_spelling_of_north_korea(self) -> None:
        """Flags use their own spellings; addresses say "Korea, North"."""
        assert iso2_for("Democratic People's Republic of Korea") == "KP"
        assert iso2_for("Korea, North") == "KP"

    def test_the_several_spellings_of_one_country_agree(self) -> None:
        assert {
            iso2_for(name)
            for name in ("St Kitts & Nevis", "St. Kitts and Nevis", "Saint Kitts and Nevis")
        } == {"KN"}

    def test_ofacs_explicit_unknowns(self) -> None:
        assert iso2_for("Unknown") == UNKNOWN_COUNTRY
        assert iso2_for("None Identified") == UNKNOWN_COUNTRY
        assert iso2_for("") == UNKNOWN_COUNTRY

    def test_a_region_inside_one_iso_country_resolves_to_it(self) -> None:
        assert iso2_for("Region: Crimea") == "UA"
        assert iso2_for("Region: West Bank") == "PS"

    def test_a_region_iso_splits_between_states_stays_unknown(self) -> None:
        """Picking a side would be a political claim, not a lookup."""
        assert iso2_for("Region: Jammu and Kashmir") == UNKNOWN_COUNTRY
        assert iso2_for("Region: Commonwealth of Independent States") == UNKNOWN_COUNTRY

    def test_an_unmapped_name_fails_the_build_loudly(self) -> None:
        """A spelling OFAC added since is something to look at, not to bury."""
        with pytest.raises(BundleError, match="No ISO 3166-1 alpha-2 code"):
            iso2_for("Wakanda")

    def test_every_mapped_code_is_well_formed(self) -> None:
        for name, code in COUNTRY_ISO2.items():
            assert len(code) == 2 and code.isalpha() and code.isupper(), name


class TestCountryFor:
    """One country per entity, out of several addresses or none."""

    def test_the_first_address_by_add_num_wins(self) -> None:
        addresses = [
            {"add_num": "20", "country": "Cyprus"},
            {"add_num": "9", "country": "Russia"},
        ]
        assert country_for(_entity(), addresses) == "RU"

    def test_an_address_row_with_no_country_is_skipped(self) -> None:
        """OFAC publishes empty address rows; they are not an answer."""
        addresses = [
            {"add_num": "1", "country": ""},
            {"add_num": "2", "country": "Iran"},
        ]
        assert country_for(_entity(), addresses) == "IR"

    def test_a_vessel_falls_back_to_its_flag(self) -> None:
        """For a ship the flag is the country that actually matters."""
        vessel = _entity(sdn_type="vessel", flag="Panama")
        assert country_for(vessel, [{"add_num": "1", "country": ""}]) == "PA"

    def test_an_address_still_beats_a_flag(self) -> None:
        vessel = _entity(sdn_type="vessel", flag="Panama")
        assert country_for(vessel, [{"add_num": "1", "country": "Liberia"}]) == "LR"

    def test_no_address_and_no_flag_is_unknown(self) -> None:
        assert country_for(_entity(), []) == UNKNOWN_COUNTRY


class TestSelectEntities:
    """In-scope programmes, capped per programme, deterministic."""

    def test_an_out_of_scope_programme_is_dropped(self) -> None:
        assert is_in_scope(("CUBA",)) == ()
        selected, _ = select_entities([_entity(program="CUBA")])
        assert selected == []

    def test_programmes_are_matched_by_prefix(self) -> None:
        """A new executive order should be picked up without editing the list."""
        assert is_in_scope(("RUSSIA-EO99999",)) == ("RUSSIA-EO99999",)

    def test_the_cap_is_enforced_per_programme(self) -> None:
        entities = [_entity(ent_num=i, name=f"E{i}") for i in range(10)]
        selected, tally = select_entities(entities, cap=4)
        assert len(selected) == 4
        assert tally["RUSSIA-EO14024"] == 4

    def test_selection_follows_ent_num_order_not_file_order(self) -> None:
        """Oldest designations survive the cap, so recognisable names remain."""
        entities = [_entity(ent_num=n, name=f"E{n}") for n in (90, 3, 50, 1)]
        selected, _ = select_entities(entities, cap=2)
        assert [e.ent_num for e in selected] == [1, 3]

    def test_a_full_programme_does_not_block_an_entity_with_room_elsewhere(self) -> None:
        """Otherwise a big programme would starve every one it overlaps."""
        entities = [_entity(ent_num=i, name=f"R{i}") for i in range(3)]
        entities.append(_entity(ent_num=99, name="BOTH", program="RUSSIA-EO14024] [DPRK4"))
        selected, tally = select_entities(entities, cap=3)
        assert "BOTH" in [e.name for e in selected]
        # It counts against both, so a full programme's tally can exceed the cap.
        assert tally["RUSSIA-EO14024"] == 4
        assert tally["DPRK4"] == 1

    def test_no_programme_is_silently_dropped(self) -> None:
        """What a plain "first N rows" selection would have got wrong."""
        entities = [_entity(ent_num=i, name=f"R{i}") for i in range(20)]
        entities.append(_entity(ent_num=999, name="LONE DPRK", program="DPRK4"))
        selected, tally = select_entities(entities, cap=5)
        assert "LONE DPRK" in [e.name for e in selected]
        assert tally["DPRK4"] == 1


class TestBuildRows:
    """Mapping onto the four columns the schema actually has."""

    def test_the_programmes_land_in_list_source(self) -> None:
        rows, _ = build_rows(
            [_entity(program="UKRAINE-EO13662] [RUSSIA-EO14024")], {}, SNAPSHOT_DATE
        )
        assert rows[0].list_source == f"{LIST_NAME} — UKRAINE-EO13662/RUSSIA-EO14024"

    def test_out_of_scope_programmes_are_not_named(self) -> None:
        rows, _ = build_rows([_entity(program="IRAN] [CUBA")], {}, SNAPSHOT_DATE)
        assert "CUBA" not in rows[0].list_source

    def test_every_row_carries_the_snapshot_date(self) -> None:
        """OFAC's CSV has no per-entity listing date, so this is what there is."""
        rows, _ = build_rows([_entity()], {}, SNAPSHOT_DATE)
        assert rows[0].date_added == SNAPSHOT_DATE

    def test_a_duplicate_name_is_collapsed_and_counted(self) -> None:
        """`sanctioned_entities.name` is a PRIMARY KEY, so it has to be."""
        rows, collapsed = build_rows(
            [_entity(ent_num=1, name="SAME"), _entity(ent_num=2, name="SAME")], {}, SNAPSHOT_DATE
        )
        assert len(rows) == 1
        assert collapsed == 1

    def test_the_first_occurrence_wins(self) -> None:
        rows, _ = build_rows(
            [
                _entity(ent_num=1, name="SAME", program="IRAN"),
                _entity(ent_num=2, name="SAME", program="DPRK4"),
            ],
            {},
            SNAPSHOT_DATE,
        )
        assert rows[0].list_source.endswith("IRAN")


class TestTheCommittedBundle:
    """The real committed file, spot-checked rather than trusted."""

    @pytest.fixture(scope="class")
    def rows(self) -> list:
        with BUNDLE.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def test_it_is_committed_and_readable(self, rows: list) -> None:
        assert BUNDLE.exists()
        assert len(rows) == 5103

    def test_the_columns_match_the_schema(self, rows: list) -> None:
        assert set(rows[0]) == {"name", "country", "list_source", "date_added"}

    def test_every_country_is_an_iso_alpha_2_code(self, rows: list) -> None:
        bad = {
            r["country"] for r in rows if not (len(r["country"]) == 2 and r["country"].isupper())
        }
        assert not bad

    def test_the_unknown_country_count_is_pinned(self, rows: list) -> None:
        """OFAC genuinely lists people with no address and no nationality."""
        assert sum(1 for r in rows if r["country"] == UNKNOWN_COUNTRY) == 517

    def test_every_row_names_the_sdn_list(self, rows: list) -> None:
        assert all(r["list_source"].startswith(LIST_NAME) for r in rows)

    def test_one_snapshot_date_for_the_whole_bundle(self, rows: list) -> None:
        assert {r["date_added"] for r in rows} == {SNAPSHOT_DATE}

    def test_names_are_unique(self, rows: list) -> None:
        assert len({r["name"] for r in rows}) == len(rows)

    def test_no_name_collides_with_the_invented_fixture_entities(self, rows: list) -> None:
        """Or a real row would overwrite a pinned worked example."""
        invented = {e.name for e in SANCTIONED_ENTITIES}
        assert not invented & {r["name"] for r in rows}

    def test_a_known_real_entity_is_present_with_its_real_metadata(self, rows: list) -> None:
        by_name = {r["name"]: r for r in rows}
        gazprom = by_name["GAZPROM INVEST, OOO"]
        assert gazprom["country"] == "RU"
        assert "RUSSIA-EO14024" in gazprom["list_source"]

    def test_only_in_scope_programmes_appear(self, rows: list) -> None:
        for row in rows:
            programmes = row["list_source"].split("—", 1)[1].strip().split("/")
            assert is_in_scope(tuple(programmes)) == tuple(programmes), row["name"]

    def test_the_bundle_stays_inside_its_latency_budget(self, rows: list) -> None:
        """A guard, not a benchmark.

        `screen_entity` takes no `limit` on purpose — truncating a hit list
        would be a compliance failure — so every entity is scored on every
        screen, at a measured ~70 us each. This is what stops someone quietly
        swapping in the full 19,391-entry list and tripling the latency of
        `/screen`, `/assess-risk` and `/sap-gts/compliance-check` at once.
        """
        assert len(rows) + len(SANCTIONED_ENTITIES) <= 6000


class TestUpsertEntities:
    """The new idempotent writer. `_seed_if_empty` could not do this."""

    @pytest.fixture
    def conn(self) -> sqlite3.Connection:
        connection = get_connection(":memory:")
        seed(connection)
        return connection

    def test_it_adds_to_an_already_populated_table(self, conn: sqlite3.Connection) -> None:
        """The whole point: seed() has already written the 18."""
        before = len(fetch_all_entities(conn))
        upsert_entities(
            conn, [SanctionedEntity("NEW CO", "RU", "US OFAC SDN — IRAN", "2026-09-22")]
        )
        assert len(fetch_all_entities(conn)) == before + 1

    def test_rewriting_a_name_updates_it_rather_than_failing(
        self, conn: sqlite3.Connection
    ) -> None:
        upsert_entities(conn, [SanctionedEntity("DUP CO", "RU", "first", "2026-01-01")])
        upsert_entities(conn, [SanctionedEntity("DUP CO", "IR", "second", "2026-02-02")])
        stored = {e.name: e for e in fetch_all_entities(conn)}["DUP CO"]
        assert (stored.country, stored.list_source, stored.date_added) == (
            "IR",
            "second",
            "2026-02-02",
        )


class TestLoadingTheBundle:
    """Additive and idempotent, exactly like the CN nomenclature bundle."""

    @pytest.fixture
    def loaded(self) -> sqlite3.Connection:
        conn = get_connection(":memory:")
        seed(conn)
        load_bundled_sanctions(conn)
        return conn

    def test_the_invented_entities_are_supplemented_not_replaced(
        self, loaded: sqlite3.Connection
    ) -> None:
        names = {e.name for e in fetch_all_entities(loaded)}
        assert {e.name for e in SANCTIONED_ENTITIES} <= names
        assert len(names) == len(SANCTIONED_ENTITIES) + 5103

    def test_loading_twice_changes_nothing(self, loaded: sqlite3.Connection) -> None:
        before = len(fetch_all_entities(loaded))
        load_bundled_sanctions(loaded)
        assert len(fetch_all_entities(loaded)) == before

    def test_seed_alone_leaves_the_corpus_invented(self) -> None:
        """Why every pinned test is unaffected: they never load the bundle."""
        conn = get_connection(":memory:")
        seed(conn)
        assert len(fetch_all_entities(conn)) == len(SANCTIONED_ENTITIES)
        assert not [e for e in fetch_all_entities(conn) if e.list_source.startswith(LIST_NAME)]


class TestScreeningRealEntities:
    """The point of the whole phase: real listed parties screen as hits."""

    @pytest.fixture(scope="class")
    def loaded(self) -> sqlite3.Connection:
        conn = get_connection(":memory:")
        seed(conn)
        load_bundled_sanctions(conn)
        return conn

    def test_a_real_listed_company_is_an_exact_hit(self, loaded: sqlite3.Connection) -> None:
        matches = screen_entity(loaded, "GAZPROM INVEST, OOO")
        assert matches[0].entity.name == "GAZPROM INVEST, OOO"
        assert matches[0].score == pytest.approx(1.0)
        assert matches[0].entity.list_source.startswith(LIST_NAME)

    def test_a_partial_name_in_different_case_still_hits(self, loaded: sqlite3.Connection) -> None:
        """What the token-overlap signal exists for, now against real data."""
        matches = screen_entity(loaded, "Gazprom Invest")
        assert matches[0].entity.name == "GAZPROM INVEST, OOO"
        assert matches[0].score == pytest.approx(1.0)

    def test_a_real_listed_bank_hits(self, loaded: sqlite3.Connection) -> None:
        assert screen_entity(loaded, "Bank Melli Iran")[0].entity.name == "BANK MELLI IRAN"

    def test_a_distinctive_single_word_hits_every_record_carrying_it(
        self, loaded: sqlite3.Connection
    ) -> None:
        """ "Sberbank" alone used to return nothing: a false negative in a compliance tool."""
        matches = screen_entity(loaded, "Sberbank")
        assert len(matches) >= 10
        assert all("SBERBANK" in m.entity.name.upper() for m in matches)
        assert screen_entity(loaded, "sberbank") == matches

    @pytest.mark.parametrize("word", ["Company", "Bank", "Mohammad", "Trading"])
    def test_a_common_single_word_does_not_flood_the_results(
        self, loaded: sqlite3.Connection, word: str
    ) -> None:
        """Hundreds of records carry these; a one-word query must not match them all."""
        assert len(screen_entity(loaded, word)) < 10

    def test_an_invented_name_screens_clean_against_real_data(
        self, loaded: sqlite3.Connection
    ) -> None:
        assert screen_entity(loaded, "Quokka Beachwear Collective") == []


class TestTheInventedEntitiesStillBehave:
    """Every pinned worked example in this project rests on these."""

    @pytest.fixture
    def conn(self) -> sqlite3.Connection:
        connection = get_connection(":memory:")
        seed(connection)
        return connection

    def test_there_are_still_exactly_eighteen(self, conn: sqlite3.Connection) -> None:
        assert len(SANCTIONED_ENTITIES) == 18

    def test_northwind_is_still_an_exact_hit(self, conn: sqlite3.Connection) -> None:
        """The name behind the 0.6609 composite and matching.py's docstring."""
        matches = screen_entity(conn, "Northwind Maritime Holdings Ltd")
        assert matches[0].score == pytest.approx(1.0)
        assert matches[0].entity.country == "CY"
        assert matches[0].entity.list_source == "EU Consolidated Financial Sanctions List"

    def test_the_partial_name_example_from_matching_py_still_holds(
        self, conn: sqlite3.Connection
    ) -> None:
        matches = screen_entity(conn, "Northwind Maritime")
        assert matches[0].entity.name == "Northwind Maritime Holdings Ltd"
        assert matches[0].score == pytest.approx(1.0)

    def test_northwind_remains_reachable_with_the_real_bundle_loaded(self) -> None:
        """The fixture must not be drowned out by 5,103 real neighbours."""
        conn = get_connection(":memory:")
        seed(conn)
        load_bundled_sanctions(conn)
        matches = screen_entity(conn, "Northwind Maritime Holdings Ltd")
        assert matches[0].entity.name == "Northwind Maritime Holdings Ltd"
        assert matches[0].score == pytest.approx(1.0)


class TestAttribution:
    """A compliance-adjacent honesty requirement, so it is a test."""

    def test_the_served_page_names_ofac_and_the_public_domain_basis(self) -> None:
        page = (
            Path(__file__).parent.parent / "src" / "customsiq" / "static" / "index.html"
        ).read_text(encoding="utf-8")
        assert page.count("17 U.S.C.") == 3, "all three languages must state the licence basis"
        assert page.count("OFAC") >= 3
        assert page.count(SNAPSHOT_DATE.replace("-", "")) == 0  # dates are written out, not packed

    @pytest.mark.parametrize("readme", ["README.md", "README.tr.md", "README.de.md"])
    def test_every_readme_attributes_ofac(self, readme: str) -> None:
        text = (Path(__file__).parent.parent / readme).read_text(encoding="utf-8")
        assert "OFAC" in text
        assert "17 U.S.C." in text, f"{readme} must state the public-domain basis"
        assert SNAPSHOT_DATE in text, f"{readme} must state the snapshot date"

    @pytest.mark.parametrize("readme", ["README.md", "README.tr.md", "README.de.md"])
    def test_no_readme_still_calls_the_sanctions_list_fictional(self, readme: str) -> None:
        """The claim this phase exists to retire.

        Checked as a co-occurrence rather than a word ban: the duty rates and the
        18 fixture entities really are invented, so "fictional" must still be
        allowed to appear — just never in the same breath as the sanctions list
        being mock data.
        """
        text = (Path(__file__).parent.parent / readme).read_text(encoding="utf-8")
        for claim in (
            "sanctioned-party list and duty/tariff rates are still fictional",
            "Every name in this list is fictional",
        ):
            assert claim not in text, f"{readme} still claims: {claim}"

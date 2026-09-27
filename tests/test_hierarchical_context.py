"""Tests for the hierarchical context that dependent CN leaves were missing.

Half the real nomenclature's leaves describe themselves only relative to a
parent they never name — "Other", "For feeding purpose" — because the source
CIRCABC sheets are hierarchical and a child row does not repeat its ancestors'
text. Scoring those against a query means scoring a fragment, which is how
"live leeches for medical purposes" reached four petroleum residues called
"For other purposes".

Two halves, tested separately:

- the bundle builder reconstructing the ancestor chain from `Hier. Pos.` and
  `Indent` (pure functions, no workbook needed), and
- `classify()` reading it, with every already-pinned real-corpus value
  re-verified rather than assumed.

`search()` is deliberately *not* wired to this and is pinned unchanged here:
difflib's `ratio()` is `2*M/T` over the combined length, so appending ancestors
can only lower a short fragment's score. Measured over five breadcrumb variants,
three left the top-3 byte-identical and two moved it the wrong way. The
`TestSearchIsDeliberatelyUntouched` class below is what keeps that decision
honest if someone later wires it in without re-measuring.
"""

import csv
import sqlite3
from pathlib import Path

import pytest

from scripts.import_cn_codes import (
    CONTEXT_ANCESTORS,
    SheetRow,
    ancestor_context,
    context_positions,
    hierarchy_depth,
    is_generic,
    needs_context,
    walk_ancestors,
)
from src.customsiq.cn_classifier import _with_context, classify
from src.customsiq.database import (
    fetch_all_contexts,
    get_connection,
    load_bundled_cn_nomenclature,
    seed,
)
from src.customsiq.search import search

BUNDLE = Path(__file__).parent.parent / "data" / "cn_nomenclature_2026.csv"

#: The real target of the "live leeches" query. No row in the EU nomenclature
#: contains the word "leech" — verified against all 25,846 source rows — so
#: leeches fall to the residual basket for other live animals. Its own text is
#: "Other", under a parent that is *also* "Other", which makes this one row both
#: the headline case and the nested-generic edge case.
LEECH_BASKET = "0106900090"


def _row(hier_position, indent, description, code="0100000000", suffix="80"):
    """A SheetRow with only the fields the hierarchy walk reads."""
    return SheetRow(code, suffix, hier_position, indent, description)


class TestHierarchyDepth:
    """`Indent` is authoritative; `Hier. Pos.` only places the top two levels."""

    def test_a_chapter_is_the_root(self) -> None:
        assert hierarchy_depth(2, None) == 0

    def test_a_heading_sits_under_its_chapter(self) -> None:
        assert hierarchy_depth(4, None) == 1

    def test_indent_dashes_count_the_remaining_levels(self) -> None:
        assert hierarchy_depth(6, "- ") == 2
        assert hierarchy_depth(6, "- - ") == 3
        assert hierarchy_depth(8, "- - - ") == 4

    def test_the_same_hier_position_can_span_two_indent_levels(self) -> None:
        """Why `Indent` wins and `Hier. Pos.` cannot be used alone.

        `0102292100` is real: it appears at `Hier. Pos.` 8 twice, once as a
        non-declarable grouping header and once as the declarable row beneath
        it. Reading the level off `Hier. Pos.` would make a row its own sibling.
        """
        assert hierarchy_depth(8, "- - - - ") == 5
        assert hierarchy_depth(8, "- - - - - ") == 6

    def test_a_missing_indent_at_a_deep_level_does_not_crash(self) -> None:
        assert hierarchy_depth(10, None) == 1


class TestWalkAncestors:
    """The stack walk, on the real shape of chapter 1's opening rows."""

    def test_the_real_opening_rows_of_chapter_one(self) -> None:
        rows = [
            _row(2, None, "LIVE ANIMALS"),
            _row(4, None, "Live horses, asses, mules and hinnies"),
            _row(6, "- ", "Horses"),
            _row(6, "- - ", "Pure-bred breeding animals"),
            _row(6, "- - ", "Other"),
            _row(8, "- - - ", "For slaughter"),
        ]
        chains = [ancestors for _, ancestors in walk_ancestors(rows)]
        assert chains[0] == []
        assert chains[2] == ["LIVE ANIMALS", "Live horses, asses, mules and hinnies"]
        assert chains[3] == ["LIVE ANIMALS", "Live horses, asses, mules and hinnies", "Horses"]
        # "Other" replaces its sibling at the same depth rather than nesting
        # under it, which is the whole point of keying the stack by depth.
        assert chains[4] == chains[3]
        assert chains[5] == [*chains[4], "Other"]

    def test_a_shallower_row_closes_every_deeper_branch(self) -> None:
        rows = [
            _row(2, None, "CHAPTER"),
            _row(4, None, "First heading"),
            _row(6, "- ", "Deep"),
            _row(6, "- - ", "Deeper"),
            _row(4, None, "Second heading"),
            _row(6, "- ", "Fresh branch"),
        ]
        chains = [ancestors for _, ancestors in walk_ancestors(rows)]
        assert chains[4] == ["CHAPTER"], "the previous heading's subtree must be closed"
        assert chains[5] == ["CHAPTER", "Second heading"]

    def test_a_depth_jump_is_tolerated_not_rejected(self) -> None:
        """Chapter 99 really does this — one jump in 25,846 source rows.

        Its single heading holds a bulleted list of goods instead of a subtree,
        so its children land two levels deeper than their parent. The chain is
        still correct, just shorter, so the walk must not assume contiguity.
        """
        rows = [_row(2, None, "CHAPTER"), _row(4, None, "Heading"), _row(10, "- - - ", "Leaf")]
        chains = [ancestors for _, ancestors in walk_ancestors(rows)]
        assert chains[2] == ["CHAPTER", "Heading"]


class TestNeedsContext:
    """Which leaves get enriched — and, just as importantly, which do not."""

    @pytest.mark.parametrize(
        "description",
        ["Other", "others", "For feeding purpose", "Of cotton", "Containing hazelnuts", "With..."],
    )
    def test_a_dependent_fragment_needs_context(self, description: str) -> None:
        assert needs_context(description)

    @pytest.mark.parametrize(
        "description",
        ["Hazelnuts", "Optical glass", "T-shirts", "Live horses", "Cows", "Pigeons"],
    )
    def test_a_description_that_stands_alone_is_left_alone(self, description: str) -> None:
        """The reason every pinned exact-match score survives untouched."""
        assert not needs_context(description)

    def test_a_word_that_merely_starts_with_an_opener_is_not_dependent(self) -> None:
        """The rule matches whole words, so "Offal" is not "Of"."""
        assert not needs_context("Offal")
        assert not needs_context("Toys")
        assert not needs_context("Information technology products")

    def test_generic_recognises_only_bare_residuals(self) -> None:
        assert is_generic("Other")
        assert is_generic("  others.  ")
        assert not is_generic("Other locks")


class TestContextPositions:
    """Chapter dropped, residual ancestors skipped, nearest `keep` retained."""

    def test_the_chapter_is_never_kept(self) -> None:
        assert context_positions(["CHAPTER", "Heading", "Subheading"]) == [1, 2]

    def test_a_residual_ancestor_is_skipped(self) -> None:
        """The nested-generic case, handled by the general rule not a special one."""
        assert context_positions(["CHAPTER", "Other live animals", "Other"]) == [1]

    def test_only_the_nearest_ancestors_are_kept(self) -> None:
        chain = ["CHAPTER", "One", "Two", "Three", "Four"]
        assert context_positions(chain) == [3, 4]
        assert len(context_positions(chain)) == CONTEXT_ANCESTORS

    def test_a_chain_with_nothing_usable_yields_no_context(self) -> None:
        assert context_positions(["CHAPTER"]) == []
        assert context_positions(["CHAPTER", "Other", "Other"]) == []
        assert ancestor_context(["CHAPTER"], []) == ""

    def test_positions_chosen_in_english_read_another_languages_chain(self) -> None:
        """Why positions rather than text: no per-language residual word lists.

        All 13,733 leaves have equal-length chains in all three exports
        (verified), so the English decision transfers positionally. Picking the
        German text by filtering German would mean teaching `is_generic` that
        "andere" is the residual there, and "autres" in French, and so on.
        """
        english = ["LIVE ANIMALS", "Other live animals", "Other"]
        german = ["LEBENDE TIERE", "Andere Tiere, lebend", "andere"]
        positions = context_positions(english)
        assert ancestor_context(english, positions) == "Other live animals"
        assert ancestor_context(german, positions) == "Andere Tiere, lebend"


class TestWithContext:
    """The one composition step on the reading side."""

    def test_context_is_prepended(self) -> None:
        assert _with_context("Other", "Other live animals") == "Other live animals > Other"

    def test_no_context_leaves_the_description_identical(self) -> None:
        assert _with_context("Hazelnuts", None) == "Hazelnuts"
        assert _with_context("Hazelnuts", "") == "Hazelnuts"

    def test_an_untranslated_code_is_not_resurrected_by_its_ancestors(self) -> None:
        """A code with no text in this language must stay absent, not score on context."""
        assert _with_context("", "Other live animals") == ""


class TestTheCommittedBundleCarriesContext:
    """Guards the fixtures below from silently testing an empty feature."""

    @pytest.fixture(scope="class")
    def rows(self) -> list:
        with BUNDLE.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def test_the_three_context_columns_are_present(self, rows: list) -> None:
        assert {"context_en", "context_de", "context_fr"} <= set(rows[0])

    def test_about_half_the_corpus_carries_context(self, rows: list) -> None:
        """Pinned exactly: a silent change to `needs_context` moves this number."""
        assert sum(1 for row in rows if row["context_en"]) == 7095
        assert len(rows) == 13733

    def test_context_is_present_in_all_three_languages_or_none(self, rows: list) -> None:
        """The dependent decision is made once, from English, for all languages."""
        for row in rows:
            present = {bool(row[f"context_{language}"]) for language in ("en", "de", "fr")}
            assert len(present) == 1, row["cn_code"]

    def test_a_row_that_stands_alone_has_no_context(self, rows: list) -> None:
        by_code = {row["cn_code"]: row for row in rows}
        assert by_code["2008191930"]["description_en"] == "Hazelnuts"
        assert by_code["2008191930"]["context_en"] == ""

    def test_the_leech_basket_reaches_past_its_residual_parent(self, rows: list) -> None:
        """The headline case and the nested-generic case in one row."""
        row = {r["cn_code"]: r for r in rows}[LEECH_BASKET]
        assert row["description_en"] == "Other"
        assert row["context_en"] == "Other live animals"
        assert row["context_de"] == "Andere Tiere, lebend"
        assert row["context_fr"] == "Autres animaux vivants"

    def test_no_row_in_the_nomenclature_mentions_leeches(self, rows: list) -> None:
        """The honest limit of the source data, pinned so the README stays true.

        This is not something breadcrumb enrichment can fix: the EU nomenclature
        simply has no term for leeches, so no amount of context will produce a
        word match. The basket code above is the correct answer and the best any
        text-matching approach can reach.
        """
        assert not [
            row for row in rows if "leech" in row["description_en"].lower()
        ], "a real 'leech' row now exists — the README's stated limit needs revisiting"


@pytest.fixture(scope="module")
def bundle() -> sqlite3.Connection:
    """Sample data plus the real committed bundle. Built once — 13.7k codes."""
    conn = get_connection(":memory:")
    seed(conn)
    load_bundled_cn_nomenclature(conn)
    return conn


class TestContextIsLoaded:
    def test_every_language_is_stored(self, bundle: sqlite3.Connection) -> None:
        for language in ("en", "de", "fr"):
            assert len(fetch_all_contexts(bundle, language)) == 7095

    def test_english_is_a_real_row_here_unlike_in_translations(
        self, bundle: sqlite3.Connection
    ) -> None:
        """A leaf's context is missing in English too, so English is stored."""
        assert fetch_all_contexts(bundle, "en")[LEECH_BASKET] == "Other live animals"
        assert fetch_all_contexts(bundle, None)[LEECH_BASKET] == "Other live animals"

    def test_a_standalone_leaf_has_no_row_at_all(self, bundle: sqlite3.Connection) -> None:
        assert "2008191930" not in fetch_all_contexts(bundle, "en")

    def test_sample_data_alone_has_no_contexts(self) -> None:
        """The mock corpus every SAMPLE_DATA-pinned score runs against."""
        conn = get_connection(":memory:")
        seed(conn)
        assert fetch_all_contexts(conn, "en") == {}


class TestTheReportedBugIsFixed:
    """The query from the report, against the real corpus."""

    QUERY = "live leeches for medical purposes"

    def test_the_leech_basket_is_now_reachable(self, bundle: sqlite3.Connection) -> None:
        """Before: absent from the top 5 entirely. After: rank 4."""
        codes = [result.hs_code.code for result in classify(bundle, self.QUERY, top_n=5)]
        assert LEECH_BASKET in codes

    def test_the_petroleum_residues_no_longer_fill_the_results(
        self, bundle: sqlite3.Connection
    ) -> None:
        """Before this fix ranks 2-5 were all "For other purposes" from chapter 27.

        They matched on "purposes" alone, with nothing in the fragment to say
        they were petroleum. Their contexts now say so, which is what demotes
        them.
        """
        results = classify(bundle, self.QUERY, top_n=5)
        petroleum = [r for r in results if r.hs_code.code.startswith("27")]
        assert len(petroleum) <= 1, [r.hs_code.code for r in results]

    def test_a_medically_relevant_row_now_ranks(self, bundle: sqlite3.Connection) -> None:
        """ "medical purposes" reaches the surgical/medical articles heading."""
        codes = [result.hs_code.code for result in classify(bundle, self.QUERY, top_n=5)]
        assert "48189010" in codes

    def test_live_animal_rows_outrank_the_residues(self, bundle: sqlite3.Connection) -> None:
        results = {r.hs_code.code: r.score for r in classify(bundle, self.QUERY, top_n=5)}
        assert results[LEECH_BASKET] > min(results.values())


class TestSearchIsDeliberatelyUntouched:
    """Pinned so wiring context into search() cannot pass silently.

    Every number here was measured before the change and is unchanged after it.
    search() scores `hs_codes.description`, which this phase left byte-identical.
    """

    @pytest.mark.parametrize(
        ("query", "score", "code"),
        [
            ("ipek kumaş", 0.4762, "17019910"),
            ("örgü pamuklu gömlek", 0.4000, "2931100010"),
            ("leather jacket", 0.5600, "83014090"),
            ("çelik boru", 0.5455, "11010090"),
            ("live leeches for medical purposes", 0.5926, "93069010"),
        ],
    )
    def test_the_calibration_corpus_scores_exactly_as_before(
        self, bundle: sqlite3.Connection, query: str, score: float, code: str
    ) -> None:
        top = search(bundle, query, limit=1)[0]
        assert top.hs_code.code == code
        assert top.score == pytest.approx(score, abs=1e-4)

    def test_the_low_confidence_threshold_still_separates_the_calibration_set(
        self, bundle: sqlite3.Connection
    ) -> None:
        """0.50 still sits where the calibration phase put it."""
        assert search(bundle, "ipek kumaş", limit=1)[0].score < 0.5
        assert search(bundle, "örgü pamuklu gömlek", limit=1)[0].score < 0.5
        assert search(bundle, "leather jacket", limit=1)[0].score > 0.5
        assert search(bundle, "çelik boru", limit=1)[0].score > 0.5


class TestPinnedExactMatchesSurvive:
    """The scores this change was designed not to move."""

    def test_the_german_hazelnut_example_still_scores_a_flat_one(
        self, bundle: sqlite3.Connection
    ) -> None:
        """The translated-matching phase's headline example, both engines."""
        assert search(bundle, "Haselnüsse", limit=1, language="de")[0].score == pytest.approx(1.0)
        top = classify(bundle, "Haselnüsse", top_n=1, language="de")[0]
        assert top.hs_code.code == "2008191930"
        assert top.score == pytest.approx(1.0)

    def test_english_exact_matches_are_still_exact(self, bundle: sqlite3.Connection) -> None:
        """A query equal to a standalone leaf's text is still a perfect cosine."""
        for query in ("hazelnuts", "optical glass"):
            assert classify(bundle, query, top_n=1)[0].score == pytest.approx(1.0)

    def test_english_is_still_never_weakened_by_asking_for_german(
        self, bundle: sqlite3.Connection
    ) -> None:
        english = classify(bundle, "knitted cotton shirt", top_n=1)
        german = classify(bundle, "knitted cotton shirt", top_n=1, language="de")
        assert german[0].hs_code.code == english[0].hs_code.code
        assert german[0].score == pytest.approx(english[0].score)

"""/search and /classify on one scoring engine.

Search used to rank with difflib character overlap, a different algorithm from
classify()'s TF-IDF. That was a documented, deliberate split, and it was
reversed after six everyday queries failed live on customsiq.org's /search.
This module pins the new architecture:

- search() is a thin adapter over classify(), identical in codes and scores;
- the six production queries, against the real committed bundle;
- `hierarchy_path`, the breadcrumb built from the stored ancestor context;
- the curated alias table, entry by entry;
- the per-heading diversity cap.
"""

import csv
import sqlite3
from pathlib import Path

import pytest

from src.customsiq import cn_classifier
from src.customsiq.cn_classifier import (
    _ALIASES,
    ALIAS_SCORE,
    MAX_PER_HEADING,
    _tokenize,
    _with_context,
    classify,
)
from src.customsiq.database import (
    fetch_all_contexts,
    get_by_code,
    get_connection,
    load_bundled_cn_nomenclature,
    seed,
)
from src.customsiq.search import search
from tests.helpers import signed_in_test_client

BUNDLE = Path(__file__).parent.parent / "data" / "cn_nomenclature_2026.csv"

# Every API route requires a session; anonymous behaviour is tested explicitly.
client = signed_in_test_client()


@pytest.fixture(scope="module")
def bundle() -> sqlite3.Connection:
    """Sample data plus the real committed bundle. Built once — 13.7k codes."""
    conn = get_connection(":memory:")
    seed(conn)
    load_bundled_cn_nomenclature(conn)
    return conn


@pytest.fixture(scope="module")
def sample_only() -> sqlite3.Connection:
    conn = get_connection(":memory:")
    seed(conn)
    return conn


@pytest.fixture(scope="module")
def bundle_codes() -> set:
    with BUNDLE.open(encoding="utf-8") as handle:
        return {row["cn_code"] for row in csv.DictReader(handle)}


class TestOneEngine:
    """search() is classify() minus the per-term reasoning."""

    @pytest.mark.parametrize(
        "query",
        ["olive oil", "bicycle", "knitted cotton shirt", "live leeches", "8517120000", "xyz"],
    )
    @pytest.mark.parametrize("language", [None, "de"])
    def test_same_codes_scores_and_paths(
        self, bundle: sqlite3.Connection, query: str, language
    ) -> None:
        searched = search(bundle, query, limit=8, language=language)
        classified = classify(bundle, query, top_n=8, language=language)
        assert [(r.hs_code.code, r.score, r.hierarchy_path, r.alias) for r in searched] == [
            (r.hs_code.code, r.score, r.hierarchy_path, r.alias) for r in classified
        ]

    def test_the_two_routes_return_the_same_ranking(self) -> None:
        searched = client.get("/search", params={"q": "honey", "limit": 5}).json()
        classified = client.get("/classify", params={"description": "honey", "top_n": 5}).json()
        assert [(r["code"], r["score"], r["hierarchy_path"]) for r in searched] == [
            (r["code"], r["score"], r["hierarchy_path"]) for r in classified
        ]

    def test_search_no_longer_pads_with_unrelated_rows(self, bundle: sqlite3.Connection) -> None:
        """difflib always filled `limit`; a query nothing shares a word with now gets []."""
        assert search(bundle, "qwxzv", limit=5) == []


#: The six queries that failed live on customsiq.org's difflib /search,
#: with the code prefix a correct answer must start with.
PRODUCTION_QUERIES = [
    ("olive oil", "15"),
    ("bicycle", "8712"),
    ("mobile phone charging cable", "8544"),
    ("honey", "0409"),
    ("leather shoes", "64"),
]


class TestProductionFailures:
    @pytest.mark.parametrize(("query", "prefix"), PRODUCTION_QUERIES)
    def test_the_correct_heading_is_in_the_top_five(
        self, bundle: sqlite3.Connection, query: str, prefix: str
    ) -> None:
        codes = [r.hs_code.code for r in search(bundle, query, limit=5, language="en")]
        assert any(code.startswith(prefix) for code in codes), codes

    def test_solar_panel_cannot_reach_8541_because_the_bundle_lacks_it(
        self, bundle: sqlite3.Connection, bundle_codes: set
    ) -> None:
        """The sixth query still fails, and why is pinned rather than hidden.

        Photovoltaic modules are heading 8541, and the committed bundle has no
        8541 row at all (it covers 871 headings, well short of the full HS). No
        scoring change can return a code that is not in the corpus. If a
        regenerated bundle adds 8541, this test fails and says to revisit.
        """
        assert not [code for code in bundle_codes if code.startswith("8541")]
        codes = [r.hs_code.code for r in search(bundle, "solar panel", limit=5)]
        assert not [code for code in codes if code.startswith("8541")]


class TestHierarchyPath:
    def test_a_dependent_leaf_carries_its_ancestors(self, bundle: sqlite3.Connection) -> None:
        results = {r.hs_code.code: r for r in search(bundle, "horses for slaughter", limit=10)}
        assert results["01012910"].hierarchy_path == (
            "Live horses, asses, mules and hinnies > Horses > For slaughter"
        )

    def test_it_reuses_the_classifier_text_verbatim(self, bundle: sqlite3.Connection) -> None:
        """No second breadcrumb builder: it is exactly what was scored."""
        contexts = fetch_all_contexts(bundle, "en")
        for result in classify(bundle, "honey", top_n=5):
            record = result.hs_code
            assert result.hierarchy_path == _with_context(
                record.description, contexts.get(record.code)
            )

    def test_a_standalone_leaf_is_just_its_description(self, bundle: sqlite3.Connection) -> None:
        top = search(bundle, "hazelnuts", limit=1)[0]
        assert top.hierarchy_path == top.hs_code.description

    def test_an_exact_code_lookup_carries_it_too(self, bundle: sqlite3.Connection) -> None:
        top = search(bundle, "0106.90.00.90")[0]
        assert top.score == 1.0
        assert top.hierarchy_path == "Other live animals > Other"

    def test_sample_data_paths_are_the_descriptions(self, sample_only: sqlite3.Connection) -> None:
        """SAMPLE_DATA has no contexts, so no path grows."""
        for result in search(sample_only, "cotton", limit=5):
            assert result.hierarchy_path == result.hs_code.description

    def test_both_routes_expose_it(self) -> None:
        for path, params in (
            ("/search", {"q": "olive oil"}),
            ("/classify", {"description": "olive oil"}),
        ):
            body = client.get(path, params=params).json()
            assert all(row["hierarchy_path"].endswith(row["description"]) for row in body)
            assert any(" > " in row["hierarchy_path"] for row in body)


class TestAliases:
    def test_the_table_is_deliberately_small(self) -> None:
        """A demo-scale illustration, not a synonym dictionary (see the comment)."""
        assert 1 <= len(_ALIASES) <= 20

    @pytest.mark.parametrize(("key", "code"), sorted(_ALIASES.items()))
    def test_every_target_exists_in_the_bundle(
        self, bundle_codes: set, key: str, code: str
    ) -> None:
        assert code in bundle_codes, f"alias {key!r} points at {code}, which is not bundled"

    @pytest.mark.parametrize(("key", "code"), sorted(_ALIASES.items()))
    def test_every_key_shares_no_word_with_its_target(
        self, bundle: sqlite3.Connection, key: str, code: str
    ) -> None:
        """An alias for a word the target already contains would paper over the scorer."""
        record = get_by_code(bundle, code)
        text = _with_context(record.description, fetch_all_contexts(bundle, "en").get(code))
        assert not set(_tokenize(key)) & set(_tokenize(text)), (key, text)

    @pytest.mark.parametrize(("key", "code"), sorted(_ALIASES.items()))
    def test_every_alias_fires_and_ranks_first(
        self, bundle: sqlite3.Connection, key: str, code: str
    ) -> None:
        top = classify(bundle, f"some {key} for sale", top_n=5)[0]
        assert top.hs_code.code == code
        assert top.score == ALIAS_SCORE
        assert top.alias == key
        assert top.matched_terms == [key]

    def test_plural_and_embedded_queries_fire(self, bundle: sqlite3.Connection) -> None:
        results = classify(bundle, "live leeches for medical purposes", top_n=5)
        assert results[0].hs_code.code == "0106900090"
        assert results[0].alias == "leech"

    def test_it_is_blended_not_a_shortcut(self, bundle: sqlite3.Connection) -> None:
        """The ordinary scored suggestions still follow the alias hit."""
        results = classify(bundle, "live leeches for medical purposes", top_n=5)
        assert len(results) == 5
        assert all(r.alias is None for r in results[1:])

    def test_a_multi_word_key_needs_every_word(self, bundle: sqlite3.Connection) -> None:
        assert all(r.alias is None for r in classify(bundle, "power supply", top_n=5))
        assert classify(bundle, "power bank", top_n=1)[0].alias == "power bank"

    def test_a_corpus_without_the_target_gets_nothing_invented(
        self, sample_only: sqlite3.Connection
    ) -> None:
        assert classify(sample_only, "leech") == []

    def test_the_api_reports_the_alias(self) -> None:
        row = client.get("/search", params={"q": "leech"}).json()[0]
        assert row["code"] == "0106900090"
        assert row["alias"] == "leech"
        assert client.get("/search", params={"q": "honey"}).json()[0]["alias"] is None


class TestHeadingCap:
    def test_no_heading_exceeds_the_cap(self, bundle: sqlite3.Connection) -> None:
        for query in ("bicycle", "leather shoes", "olive oil", "cotton"):
            codes = [r.hs_code.code[:4] for r in classify(bundle, query, top_n=10)]
            assert max(codes.count(heading) for heading in set(codes)) <= MAX_PER_HEADING

    def test_it_is_what_lets_bicycles_in(
        self, bundle: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Uncapped, five 8714 bicycle-*parts* rows fill the top five."""
        monkeypatch.setattr(cn_classifier, "MAX_PER_HEADING", 99)
        uncapped = [r.hs_code.code for r in classify(bundle, "bicycle", top_n=5)]
        assert all(code.startswith("8714") for code in uncapped)
        monkeypatch.undo()
        capped = [r.hs_code.code for r in classify(bundle, "bicycle", top_n=5)]
        assert capped[:3] == uncapped[:3]
        assert any(code.startswith("8712") for code in capped)

    def test_the_top_suggestion_never_changes(
        self, bundle: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        queries = ("bicycle", "leather shoes", "honey", "knitted cotton shirt", "steel pipe")
        capped = [classify(bundle, q, top_n=1)[0].hs_code.code for q in queries]
        monkeypatch.setattr(cn_classifier, "MAX_PER_HEADING", 99)
        assert [classify(bundle, q, top_n=1)[0].hs_code.code for q in queries] == capped

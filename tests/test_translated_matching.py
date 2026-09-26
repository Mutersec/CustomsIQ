"""Tests for matching against the bundled DE/FR nomenclature text.

`hs_code_translations` has held real EN/DE/FR descriptions for the 13,733
bundled leaf codes since the TARIC bundle landed, but matching only ever read
the English `hs_codes.description` column. These tests cover wiring the
translations in: that a German query genuinely does better, that English is
never weakened, and that a corpus with no translations behaves exactly as it
did before.

The bundle is loaded once per module — it's 13.7k codes and two TF-IDF
indexes, too slow to rebuild per test.
"""

import sqlite3

import pytest

from src.customsiq.cn_classifier import _index_cache, classify
from src.customsiq.database import (
    fetch_all_translations,
    get_connection,
    load_bundled_cn_nomenclature,
    seed,
    upsert_translations,
)
from src.customsiq.search import search

#: Real bundled code whose German text differs sharply from its English.
#: EN "Hazelnuts" / DE "Haselnüsse" — no shared token at all, which is what
#: makes it a clean demonstration rather than a coincidence of cognates.
HAZELNUT_CODE = "2008191930"


@pytest.fixture(scope="module")
def bundle() -> sqlite3.Connection:
    """Sample data plus the real committed CN bundle, with translations."""
    conn = get_connection(":memory:")
    seed(conn)
    load_bundled_cn_nomenclature(conn)
    return conn


@pytest.fixture
def sample_only() -> sqlite3.Connection:
    """SAMPLE_DATA alone — the corpus every pinned test runs against."""
    conn = get_connection(":memory:")
    seed(conn)
    return conn


class TestTheBundledTranslationsAreActuallyThere:
    """Guards the fixtures above from silently testing an empty feature."""

    def test_german_text_is_stored_and_differs_from_english(
        self, bundle: sqlite3.Connection
    ) -> None:
        german = fetch_all_translations(bundle, "de")
        assert len(german) > 13_000
        assert german[HAZELNUT_CODE] == "Haselnüsse"

    def test_french_is_stored_too(self, bundle: sqlite3.Connection) -> None:
        assert len(fetch_all_translations(bundle, "fr")) > 13_000

    def test_english_is_the_base_column_not_a_translation(self, bundle: sqlite3.Connection) -> None:
        """Asking for English costs no query and returns nothing to merge."""
        assert fetch_all_translations(bundle, "en") == {}
        assert fetch_all_translations(bundle, None) == {}


class TestGermanQueriesScoreBetter:
    """The point of the change, with the before/after numbers pinned."""

    def test_search_finds_the_german_term(self, bundle: sqlite3.Connection) -> None:
        english_only = search(bundle, "Haselnüsse", limit=1)[0]
        translated = search(bundle, "Haselnüsse", limit=1, language="de")[0]

        assert translated.score > english_only.score
        assert translated.score == pytest.approx(1.0)
        assert translated.hs_code.code == HAZELNUT_CODE

    def test_classify_finds_a_code_it_could_not_find_before(
        self, bundle: sqlite3.Connection
    ) -> None:
        """The sharpest case: English-only returns nothing at all.

        "Haselnüsse" shares no token with "Hazelnuts", so TF-IDF honestly has
        nothing to go on and returns an empty list. Against the German text it
        is an exact match.
        """
        assert classify(bundle, "Haselnüsse", language=None) == []

        translated = classify(bundle, "Haselnüsse", top_n=1, language="de")
        assert translated
        assert translated[0].hs_code.code == HAZELNUT_CODE
        assert translated[0].score == pytest.approx(1.0)

    def test_french_works_through_the_same_mechanism(self, bundle: sqlite3.Connection) -> None:
        """Nothing about the code is German-specific."""
        french = fetch_all_translations(bundle, "fr")
        results = search(bundle, french[HAZELNUT_CODE], limit=1, language="fr")
        assert results[0].hs_code.code == HAZELNUT_CODE


class TestEnglishIsNeverWeakened:
    """The constraint that ruled out merging the languages into one document."""

    @pytest.mark.parametrize(
        "query", ["cotton t-shirt", "lithium battery", "optical glass", "mobile phone"]
    )
    def test_an_english_querys_best_answers_survive_asking_for_german(
        self, bundle: sqlite3.Connection, query: str
    ) -> None:
        """A German speaker may still type an English product name.

        The leading results are what a user actually reads, and they are
        unchanged. Deeper ranks *can* shift, and that is by design rather than
        a regression: taking the max can only raise another record's score, so
        a code whose German text happens to score higher may climb past one it
        previously sat below. No record's own score drops — the test below
        pins that separately.
        """
        english_only = search(bundle, query, limit=3)
        with_german = search(bundle, query, limit=3, language="de")
        assert [r.hs_code.code for r in with_german] == [r.hs_code.code for r in english_only]
        assert [r.score for r in with_german] == [r.score for r in english_only]

    def test_an_english_classify_is_unchanged_by_asking_for_german(
        self, bundle: sqlite3.Connection
    ) -> None:
        english_only = classify(bundle, "knitted cotton shirt", top_n=1)
        with_german = classify(bundle, "knitted cotton shirt", top_n=1, language="de")
        assert with_german[0].hs_code.code == english_only[0].hs_code.code
        assert with_german[0].score == pytest.approx(english_only[0].score)

    def test_a_records_english_score_is_never_lowered(self, bundle: sqlite3.Connection) -> None:
        """max() can only raise a score, never drop one."""
        english_only = {r.hs_code.code: r.score for r in search(bundle, "hazelnuts", limit=20)}
        translated = {
            r.hs_code.code: r.score for r in search(bundle, "hazelnuts", limit=20, language="de")
        }
        for code, score in translated.items():
            if code in english_only:
                assert score >= english_only[code] - 1e-12


class TestNoTranslationsMeansNoChange:
    """SAMPLE_DATA has zero rows in hs_code_translations — the pinned corpus."""

    def test_sample_data_has_no_translations_at_all(self, sample_only: sqlite3.Connection) -> None:
        assert fetch_all_translations(sample_only, "de") == {}

    @pytest.mark.parametrize("query", ["cotton t-shirt", "knitted cotton shirt", "Haselnüsse"])
    def test_asking_for_german_changes_nothing(
        self, sample_only: sqlite3.Connection, query: str
    ) -> None:
        """Identical results with and without a language, score for score."""
        plain = search(sample_only, query, limit=5)
        german = search(sample_only, query, limit=5, language="de")
        assert [(r.hs_code.code, r.score) for r in german] == [
            (r.hs_code.code, r.score) for r in plain
        ]

        assert classify(sample_only, query, language="de") == classify(sample_only, query)


class TestTokenizerHandlesNonAsciiText:
    """The ASCII-only regex shredded accented words — in English text too."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Haselnüsse", "haselnüsse"),
            ("Gruyère", "gruyère"),  # an accented word in an *English* description
            ("Bergkäse", "bergkäse"),
        ],
    )
    def test_accented_words_tokenize_whole(self, text: str, expected: str) -> None:
        from src.customsiq.cn_classifier import _tokenize

        assert expected in _tokenize(text)

    def test_sample_data_tokenization_is_untouched(self, sample_only: sqlite3.Connection) -> None:
        """Why the pinned scores are safe: SAMPLE_DATA is pure ASCII.

        Pinned against the ASCII regex's own output, so this fails if the
        tokenizer ever starts treating the mock corpus differently.
        """
        import re

        from src.customsiq.cn_classifier import _singular, _tokenize
        from src.customsiq.database import fetch_all

        ascii_only = re.compile(r"[a-z0-9]+")
        for record in fetch_all(sample_only):
            legacy = [_singular(w) for w in ascii_only.findall(record.description.lower())]
            assert _tokenize(record.description) == legacy, record.code


class TestIndexCacheIsPerLanguage:
    """Adding a second index must not evict the first, or serve it stale."""

    def test_each_language_gets_its_own_entry(self, bundle: sqlite3.Connection) -> None:
        classify(bundle, "cotton shirt")
        classify(bundle, "Baumwolle", language="de")
        assert (id(bundle), None) in _index_cache
        assert (id(bundle), "de") in _index_cache

    def test_an_edited_translation_is_not_served_stale(self) -> None:
        """The same freshness guarantee descriptions already had.

        A row-count or mtime check would miss this: the edit replaces one
        translation in place, leaving the row count identical.
        """
        conn = get_connection(":memory:")
        seed(conn)
        upsert_translations(conn, [("6109100000", "de", "ursprünglicher Text")])

        assert classify(conn, "ursprünglicher", language="de")[0].hs_code.code == "6109100000"

        upsert_translations(conn, [("6109100000", "de", "völlig anderer zzqxzzq Wortlaut")])
        results = classify(conn, "zzqxzzq", language="de")
        assert results, "the updated translation was not picked up — stale cache"
        assert results[0].hs_code.code == "6109100000"

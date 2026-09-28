"""Guards the single-file frontend's translation dictionary.

A missing key doesn't fail loudly in the browser: `t()` falls back to English
and, when a key is missing there too, returns `undefined` — which for the
function-valued strings means calling `undefined(...)` and taking the whole
render down inside a try/except that reports it as a network error. That is
exactly how `t("review.roleCannotReview")` (defined under `auth.`, called under
`review.`) presented while building this phase, so it is worth a test.
"""

import re
from pathlib import Path

import pytest

STATIC_DIR = Path(__file__).resolve().parents[1] / "src" / "customsiq" / "static"
INDEX = STATIC_DIR / "index.html"
LOGIN = STATIC_DIR / "login.html"
LANGUAGES = ("en", "tr", "de")


def _block(text: str, start: int) -> str:
    """Return the `{...}` block starting at `start`, brace-matched."""
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError("unbalanced braces in the translation dictionary")


@pytest.fixture(scope="module")
def source() -> str:
    return INDEX.read_text(encoding="utf-8")


def _dictionaries(source: str) -> dict:
    """The three per-language STRINGS blocks, as raw text."""
    blocks = {}
    for language in LANGUAGES:
        match = re.search(rf"\n    {language}: {{", source)
        assert match, f"no {language} block in STRINGS"
        blocks[language] = _block(source, match.end() - 1)
    return blocks


@pytest.fixture(scope="module")
def dictionaries(source: str) -> dict:
    return _dictionaries(source)


def _resolve(block: str, dotted_key: str) -> bool:
    """Whether `a.b.c` exists in one language block."""
    current = block
    parts = dotted_key.split(".")
    for part in parts[:-1]:
        match = re.search(rf"\b{re.escape(part)}: {{", current)
        if not match:
            return False
        current = _block(current, match.end() - 1)
    return re.search(rf"\b{re.escape(parts[-1])}:", current) is not None


def _used_keys(source: str) -> set:
    """Every key the script passes to t("..."), and every data-i18n attribute."""
    keys = set(re.findall(r'\bt\("([\w.]+)"\)', source))
    keys |= set(re.findall(r'data-i18n(?:-html|-placeholder)?="([\w.]+)"', source))
    return keys


def test_the_page_uses_translation_keys_at_all(source: str) -> None:
    """Guards the regexes above from silently matching nothing."""
    keys = _used_keys(source)
    assert len(keys) > 50
    assert "auth.loginToReview" in keys
    assert "review.approve" in keys


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_key_the_page_uses_exists_in_every_language(
    source: str, dictionaries: dict, language: str
) -> None:
    """EN, TR and DE must all define every key the page actually asks for."""
    missing = sorted(key for key in _used_keys(source) if not _resolve(dictionaries[language], key))
    assert not missing, f"{language} is missing: {missing}"


@pytest.mark.parametrize("language", LANGUAGES)
def test_login_page_every_key_it_uses_exists_in_every_language(language: str) -> None:
    """login.html has its own small STRINGS object — checked the same way."""
    login_source = LOGIN.read_text(encoding="utf-8")
    dictionaries = _dictionaries(login_source)
    keys = _used_keys(login_source)
    assert len(keys) > 5
    missing = sorted(key for key in keys if not _resolve(dictionaries[language], key))
    assert not missing, f"{language} is missing: {missing}"


#: QA audit Bug #4: the screening hint used to claim unqualified "partial
#: name" tolerance, when matching.py's token-overlap signal is deliberately
#: gated to names with >= 2 tokens. Each language's corrected hint must say
#: so, not just resolve as a key — the plain existence check above would
#: happily pass a hint that silently overclaims again.
_HONEST_QUALIFIER = {
    "en": "two or more",
    "tr": "iki veya daha fazla",
    "de": "zwei oder mehr",
}


def _screen_hint(block: str) -> str:
    """The literal `screen.hint` string value out of one language block."""
    match = re.search(r"\bscreen: {", block)
    assert match, "no screen block in STRINGS"
    screen_block = _block(block, match.end() - 1)
    match = re.search(r'\bhint: "((?:[^"\\]|\\.)*)"', screen_block)
    assert match, "screen.hint has no string value"
    return match.group(1)


@pytest.mark.parametrize("language", LANGUAGES)
def test_screening_hint_honestly_states_the_two_token_minimum(
    dictionaries: dict, language: str
) -> None:
    """Regression guard for the "partial names" overclaim (QA audit Bug #4)."""
    hint = _screen_hint(dictionaries[language])
    assert _HONEST_QUALIFIER[language] in hint, f"{language} screen.hint: {hint!r}"


#: Low-confidence warning: each language's copy must name the reference
#: languages the corpus is actually matched in (EN/DE/FR since translated
#: matching), not just resolve as a key. It used to say "in English" only.
_NAMES_REFERENCE_LANGUAGES = {
    "en": "(English, German or French)",
    "tr": "(İngilizce, Almanca veya Fransızca)",
    "de": "(Englisch, Deutsch oder Französisch)",
}


def _leaf_value(block: str, dotted_key: str) -> str:
    """The literal string value at `dotted_key` (e.g. "common.lowConfidence")."""
    current = block
    parts = dotted_key.split(".")
    for part in parts[:-1]:
        match = re.search(rf"\b{re.escape(part)}: {{", current)
        assert match, f"{dotted_key!r} is missing at {part!r}"
        current = _block(current, match.end() - 1)
    match = re.search(rf'\b{re.escape(parts[-1])}:\s*"((?:[^"\\]|\\.)*)"', current)
    assert match, f"{dotted_key!r} has no string value"
    return match.group(1)


@pytest.mark.parametrize("language", LANGUAGES)
def test_low_confidence_warning_names_the_reference_languages(
    dictionaries: dict, language: str
) -> None:
    """Every language's warning must point at a real fix: official wording."""
    text = _leaf_value(dictionaries[language], "common.lowConfidence")
    assert _NAMES_REFERENCE_LANGUAGES[language] in text, f"{language}: {text!r}"


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_warning_states_the_threshold_it_is_gated_on(
    source: str, dictionaries: dict, language: str
) -> None:
    """The copy says "below N%"; N must be the constant the code actually uses."""
    threshold = float(re.search(r"const LOW_CONFIDENCE_THRESHOLD = ([\d.]+);", source).group(1))
    text = _leaf_value(dictionaries[language], "common.lowConfidence")
    assert str(round(threshold * 100)) in text, f"{language}: {text!r}"


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_warning_no_longer_redirects_to_the_other_panel(
    dictionaries: dict, language: str
) -> None:
    """The "try the Classify panel" advice is gone, in every language.

    It made sense while Search used a different (difflib) engine that could
    not read the tariff hierarchy. Both panels now share one engine, so
    pointing from one to the other would send the user to the same ranking.
    """
    assert not _resolve(dictionaries[language], "common.tryClassify")
    panel = _leaf_value(dictionaries[language], "classify.title")
    assert panel not in _leaf_value(dictionaries[language], "common.lowConfidence")


def test_neither_panel_suggests_the_other(source: str) -> None:
    assert "tryClassify" not in source
    assert "suggestClassify" not in source


def test_low_confidence_threshold_exists_and_gates_both_panels(source: str) -> None:
    """A lightweight check that the served JS actually has the logic, not just copy.

    Pins the recalibrated value: 0.30, measured for the shared TF-IDF engine
    (the old 0.50 was tuned on difflib scores — see the comment next to the
    constant). Both renderers must call the same gate.
    """
    match = re.search(r"const LOW_CONFIDENCE_THRESHOLD = ([\d.]+);", source)
    assert match, "LOW_CONFIDENCE_THRESHOLD constant not found in served JS"
    assert float(match.group(1)) == 0.3

    assert "searchBox.innerHTML = lowConfidenceBanner(rows) + rows.map" in source
    assert "classifyBox.innerHTML = lowConfidenceBanner(rows) + rows.map" in source


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("key", ["common.hierarchy", "common.curatedAlias"])
def test_hierarchy_and_alias_labels_exist_in_every_language(
    dictionaries: dict, language: str, key: str
) -> None:
    assert _leaf_value(dictionaries[language], key).strip()


def test_hierarchy_labels_are_actually_translated(dictionaries: dict) -> None:
    """Not the English label copied into the other two dictionaries."""
    labels = {lang: _leaf_value(dictionaries[lang], "common.hierarchy") for lang in LANGUAGES}
    assert len(set(labels.values())) == len(LANGUAGES), labels


def test_both_result_cards_render_the_hierarchy_path(source: str) -> None:
    """Search and Classify cards both go through the one describeHtml helper."""
    assert "row.hierarchy_path" in source
    assert 't("common.hierarchy")' in source
    assert 't("common.curatedAlias")' in source
    assert source.count("${describeHtml(row)}") == 2
    assert "escapeHtml(row.description)}</p>" not in source


def test_the_page_never_sends_a_reviewer_name(source: str) -> None:
    """Identity comes from the session cookie now.

    Reading `r.reviewer_name` off a history row is fine and expected; what must
    be gone is the old header input and any attempt to *send* a name, which the
    API would ignore anyway.
    """
    assert 'id="reviewer-name"' not in source
    assert not re.search(r"reviewer_name:", source), "the page still posts a reviewer_name"
    assert re.search(r"\breviewer_name\b", source), "history rendering should still read it"

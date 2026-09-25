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


def test_the_page_never_sends_a_reviewer_name(source: str) -> None:
    """Identity comes from the session cookie now.

    Reading `r.reviewer_name` off a history row is fine and expected; what must
    be gone is the old header input and any attempt to *send* a name, which the
    API would ignore anyway.
    """
    assert 'id="reviewer-name"' not in source
    assert not re.search(r"reviewer_name:", source), "the page still posts a reviewer_name"
    assert re.search(r"\breviewer_name\b", source), "history rendering should still read it"

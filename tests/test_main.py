"""Tests for the CustomsIQ CLI entry point."""

from collections.abc import Iterator

import pytest

from src.customsiq.main import run


def _fake_input(answers: list[str]) -> callable:
    it: Iterator[str] = iter(answers)
    return lambda _prompt: next(it)


def test_run_prints_results_then_quits(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """A normal search followed by 'quit' should print a ranked result and exit."""
    monkeypatch.setattr("builtins.input", _fake_input(["cotton t-shirt", "quit"]))
    run(":memory:")
    out = capsys.readouterr().out
    assert "6109100000" in out


def test_run_handles_blank_and_invalid_query(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """A blank line is skipped, a too-long query logs a warning, then 'quit' exits."""
    monkeypatch.setattr("builtins.input", _fake_input(["", "x" * 600, "quit"]))
    run(":memory:")
    out = capsys.readouterr().out
    assert "at most" in out


def test_run_screens_a_listed_name(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """'screen <name>' runs sanctions screening and reports the hit."""
    monkeypatch.setattr("builtins.input", _fake_input(["screen Northwind Maritime", "quit"]))
    run(":memory:")
    out = capsys.readouterr().out
    assert "Northwind Maritime Holdings Ltd" in out
    assert "potential sanctions match" in out


def test_run_screens_a_clean_name(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """A name matching nothing reports a clean result rather than an error."""
    monkeypatch.setattr("builtins.input", _fake_input(["screen Quokka Beachwear", "quit"]))
    run(":memory:")
    assert "No sanctions match" in capsys.readouterr().out

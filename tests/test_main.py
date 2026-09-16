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


def test_run_classifies_a_description(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """'classify <description>' prints ranked codes and the terms behind them."""
    monkeypatch.setattr("builtins.input", _fake_input(["classify knitted cotton shirt", "quit"]))
    run(":memory:")
    out = capsys.readouterr().out
    assert "6109100000" in out
    assert "via:" in out
    assert "confidence" in out


def test_run_reports_an_unclassifiable_description(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """A description sharing no term reports that, rather than listing noise."""
    monkeypatch.setattr("builtins.input", _fake_input(["classify zephyr quokka", "quit"]))
    run(":memory:")
    assert "No code shares a term" in capsys.readouterr().out


def test_run_calculates_duty(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """'duty <code> <country> <value>' prints the amount and the reasoning."""
    monkeypatch.setattr("builtins.input", _fake_input(["duty 6109100000 CN 1000", "quit"]))
    run(":memory:")
    out = capsys.readouterr().out
    assert "120.00" in out
    assert "Standard MFN rate" in out


def test_run_reports_a_missing_duty_rate(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """A code with no rate warns instead of crashing the loop."""
    monkeypatch.setattr("builtins.input", _fake_input(["duty 99999999 CN 100", "quit"]))
    run(":memory:")
    assert "No tariff rate" in capsys.readouterr().out


def test_run_rejects_a_malformed_duty_command(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """Wrong argument count and a non-numeric value both explain themselves."""
    monkeypatch.setattr("builtins.input", _fake_input(["duty 6109100000", "duty a b c", "quit"]))
    run(":memory:")
    out = capsys.readouterr().out
    assert "Usage: duty" in out
    assert "not a number" in out


def test_run_records_and_lists_a_review(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """'review ...' records a decision and 'review-history' lists it back."""
    monkeypatch.setattr(
        "builtins.input",
        _fake_input(["review duty someref approved alice looks fine", "review-history", "quit"]),
    )
    run(":memory:")
    out = capsys.readouterr().out
    assert "Recorded: approved" in out
    assert "duty:someref  approved  by alice  (looks fine)" in out


def test_run_rejects_a_malformed_review_command(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """Too few arguments explain the expected shape instead of crashing."""
    monkeypatch.setattr("builtins.input", _fake_input(["review duty someref", "quit"]))
    run(":memory:")
    assert "Usage: review" in capsys.readouterr().out


def test_run_reports_no_review_history(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """An empty audit trail says so rather than printing nothing."""
    monkeypatch.setattr("builtins.input", _fake_input(["review-history", "quit"]))
    run(":memory:")
    assert "No review decisions recorded yet." in capsys.readouterr().out

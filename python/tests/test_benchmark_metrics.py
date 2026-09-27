"""Tests for benchmarks/metrics.py's hand-written edit-distance metrics."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "benchmarks"))

from metrics import (  # noqa: E402
    character_error_rate,
    fuzzy_match,
    normalized_edit_distance,
    word_error_rate,
)


def test_cer_identical_strings_zero():
    assert character_error_rate("hello world", "hello world") == 0.0


def test_cer_known_case():
    # "kitten" -> "sitting": edit distance 3, reference length 6.
    assert character_error_rate("kitten", "sitting") == pytest.approx(3 / 6)


def test_cer_empty_reference():
    assert character_error_rate("", "") == 0.0
    assert character_error_rate("", "abc") == 1.0


def test_wer_word_level():
    assert word_error_rate("the cat sat", "the cat sat") == 0.0
    assert word_error_rate("the cat sat", "the dog sat") == pytest.approx(1 / 3)


def test_normalized_edit_distance_bounds():
    assert 0.0 <= normalized_edit_distance("abc", "xyz") <= 1.0
    assert normalized_edit_distance("abc", "abc") == 0.0


def test_fuzzy_match_close_strings():
    assert fuzzy_match("Golden Market", "Golden Markett", threshold=0.8)
    assert not fuzzy_match("Golden Market", "Totally Different Name", threshold=0.8)


def test_fuzzy_match_both_empty():
    assert fuzzy_match("", "")

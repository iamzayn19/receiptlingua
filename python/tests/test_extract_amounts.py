"""Locale-defensive amount parsing tests."""

from __future__ import annotations

from receiptlingua.extract.amounts import parse_amount


def test_us_style_thousands_and_decimal():
    result = parse_amount("1,234.56")
    assert result.value == 1234.56
    assert not result.ambiguous


def test_european_style_thousands_and_decimal():
    result = parse_amount("1.234,56")
    assert result.value == 1234.56
    assert not result.ambiguous


def test_simple_decimal():
    result = parse_amount("12.34")
    assert result.value == 12.34
    assert not result.ambiguous


def test_ambiguous_single_separator_three_trailing_digits():
    result = parse_amount("1,234")
    assert result.ambiguous
    assert result.value is None


def test_ambiguous_single_dot_three_trailing_digits():
    result = parse_amount("1.234")
    assert result.ambiguous
    assert result.value is None


def test_pure_thousands_grouping_no_decimal():
    result = parse_amount("1,234,567")
    assert result.value == 1234567
    assert not result.ambiguous


def test_plain_integer():
    result = parse_amount("42")
    assert result.value == 42
    assert not result.ambiguous

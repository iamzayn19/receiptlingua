"""Date/time extraction tests."""

from __future__ import annotations

from receiptlingua.extract.dates import extract_date, extract_time


def test_iso_date_unambiguous():
    field = extract_date(["Store", "2024-03-15", "Total 10.00"])
    assert field.status == "ok"
    assert field.value == "2024-03-15"
    assert field.evidence.text_line_indices == (1,)


def test_numeric_date_unambiguous_because_day_over_12():
    # 25 can only be the day -> MM/DD is impossible, so DD/MM is forced.
    field = extract_date(["25/03/2024"])
    assert field.status == "ok"
    assert field.value == "2024-03-25"


def test_numeric_date_ambiguous_with_no_locale_signal():
    field = extract_date(["03/04/25"])
    assert field.status == "uncertain"
    assert "candidates" in field.value
    assert len(field.value["candidates"]) == 2


def test_rejects_impossible_day():
    field = extract_date(["32/13/2024"])
    assert field.status == "missing"


def test_month_name_date():
    field = extract_date(["15 March 2024"])
    assert field.status == "ok"
    assert field.value == "2024-03-15"


def test_time_24h():
    field = extract_time(["Time: 14:35"])
    assert field.status == "ok"
    assert field.value == "14:35:00"


def test_time_12h_pm():
    field = extract_time(["2:35 PM"])
    assert field.status == "ok"
    assert field.value == "14:35:00"


def test_time_missing():
    field = extract_time(["no time here"])
    assert field.status == "missing"

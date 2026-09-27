"""Date and time extraction with format-ambiguity awareness.

Handles the common numeric-date conventions (DD/MM/YYYY, MM/DD/YYYY,
YYYY-MM-DD) plus month-name dates, validates the result is a real calendar
date, and marks the field ``uncertain`` (rather than guessing) whenever the
day/month order is genuinely ambiguous -- e.g. "03/04/25" with no other
locale signal. ISO order (YYYY-MM-DD) and month-name dates are unambiguous
by construction. A numeric date is also unambiguous when one of the two
candidate positions is > 12 (it can only be the day).
"""

from __future__ import annotations

import calendar
import re

from receiptlingua.extract.types import Evidence, ScalarField

_MONTH_NAMES = {
    name.lower(): i
    for i, name in enumerate(calendar.month_name)
    if name
}
_MONTH_ABBR = {
    name.lower(): i
    for i, name in enumerate(calendar.month_abbr)
    if name
}

_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_NUMERIC_DATE_RE = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\b")
_MONTH_NAME_DATE_RE = re.compile(
    r"\b(\d{1,2})\s+([A-Za-z]+)\.?\s+(\d{2,4})\b|\b([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{2,4})\b"
)
_TIME_RE = re.compile(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([AaPp][Mm])?\b")


def _valid_date(year: int, month: int, day: int) -> bool:
    if year < 1000:
        year += 2000 if year < 100 else 0
    if not (1 <= month <= 12):
        return False
    try:
        last_day = calendar.monthrange(year, month)[1]
    except calendar.IllegalMonthError:
        return False
    return 1 <= day <= last_day


def _normalize_year(y: int) -> int:
    return y + 2000 if y < 100 else y


def extract_date(lines: list[str]) -> ScalarField:
    """Find and parse the first plausible date across ``lines``."""
    for idx, text in enumerate(lines):
        m = _ISO_DATE_RE.search(text)
        if m:
            year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if _valid_date(year, month, day):
                return ScalarField(
                    status="ok",
                    value=f"{year:04d}-{month:02d}-{day:02d}",
                    confidence=0.9,
                    evidence=Evidence(text_line_indices=(idx,)),
                )
            continue

        m = _MONTH_NAME_DATE_RE.search(text)
        if m:
            if m.group(2):
                day, month_name, year = int(m.group(1)), m.group(2).lower(), int(m.group(3))
            else:
                month_name, day, year = m.group(4).lower(), int(m.group(5)), int(m.group(6))
            month = _MONTH_NAMES.get(month_name) or _MONTH_ABBR.get(month_name[:3])
            if month is None:
                continue
            year = _normalize_year(year)
            if _valid_date(year, month, day):
                return ScalarField(
                    status="ok",
                    value=f"{year:04d}-{month:02d}-{day:02d}",
                    confidence=0.9,
                    evidence=Evidence(text_line_indices=(idx,)),
                )
            continue

        m = _NUMERIC_DATE_RE.search(text)
        if m:
            a, b, y = int(m.group(1)), int(m.group(2)), _normalize_year(int(m.group(3)))
            a_could_be_month = a <= 12
            b_could_be_month = b <= 12
            day_month_valid = _valid_date(y, b, a)  # DD/MM/YYYY
            month_day_valid = _valid_date(y, a, b)  # MM/DD/YYYY

            if day_month_valid and not month_day_valid:
                return ScalarField(status="ok", value=f"{y:04d}-{b:02d}-{a:02d}", confidence=0.85, evidence=Evidence(text_line_indices=(idx,)))
            if month_day_valid and not day_month_valid:
                return ScalarField(status="ok", value=f"{y:04d}-{a:02d}-{b:02d}", confidence=0.85, evidence=Evidence(text_line_indices=(idx,)))
            if day_month_valid and month_day_valid and a != b:
                # Both orders are calendar-valid and produce different
                # dates -- genuinely ambiguous without a locale signal.
                return ScalarField(
                    status="uncertain",
                    value={"candidates": [f"{y:04d}-{b:02d}-{a:02d}", f"{y:04d}-{a:02d}-{b:02d}"]},
                    confidence=0.4,
                    evidence=Evidence(text_line_indices=(idx,)),
                )
            if day_month_valid and month_day_valid:
                # a == b: identical either way.
                return ScalarField(status="ok", value=f"{y:04d}-{a:02d}-{b:02d}", confidence=0.85, evidence=Evidence(text_line_indices=(idx,)))
            continue

    return ScalarField.missing()


def extract_time(lines: list[str]) -> ScalarField:
    """Find and parse the first plausible time-of-day across ``lines``."""
    for idx, text in enumerate(lines):
        m = _TIME_RE.search(text)
        if not m:
            continue
        hour, minute = int(m.group(1)), int(m.group(2))
        second = int(m.group(3)) if m.group(3) else 0
        meridiem = m.group(4)
        if minute > 59 or second > 59:
            continue
        if meridiem:
            if not (1 <= hour <= 12):
                continue
            if meridiem.lower() == "pm" and hour != 12:
                hour += 12
            if meridiem.lower() == "am" and hour == 12:
                hour = 0
        elif hour > 23:
            continue
        return ScalarField(
            status="ok",
            value=f"{hour:02d}:{minute:02d}:{second:02d}",
            confidence=0.85,
            evidence=Evidence(text_line_indices=(idx,)),
        )
    return ScalarField.missing()

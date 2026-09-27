"""Locale-defensive numeric amount parsing.

Receipts vary in thousand/decimal separator convention: "1,234.56" (US/UK),
"1.234,56" (much of Europe/Latin America), or a single separator that is
genuinely ambiguous without more context ("1.234" could be one thousand two
hundred thirty-four, or one point two three four). Per the project's
no-hallucination constraint, ambiguous cases are reported as such rather
than resolved by a silent guess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_NUMBER_RE = re.compile(r"[0-9][0-9.,]*[0-9]|[0-9]")


@dataclass(frozen=True)
class ParsedAmount:
    value: float | None
    ambiguous: bool
    raw: str


def parse_amount(token: str) -> ParsedAmount:
    """Parse a numeric token, defensively handling separator ambiguity.

    Returns ``ambiguous=True`` (and ``value=None``) when the separator
    convention cannot be determined from the token alone.
    """
    raw = token.strip()
    cleaned = raw.replace(" ", "")
    has_comma = "," in cleaned
    has_dot = "." in cleaned

    if has_comma and has_dot:
        # Whichever separator appears last is the decimal point.
        last_comma = cleaned.rfind(",")
        last_dot = cleaned.rfind(".")
        if last_dot > last_comma:
            decimal_sep, thousand_sep = ".", ","
        else:
            decimal_sep, thousand_sep = ",", "."
        normalized = cleaned.replace(thousand_sep, "").replace(decimal_sep, ".")
        try:
            return ParsedAmount(value=float(normalized), ambiguous=False, raw=raw)
        except ValueError:
            return ParsedAmount(value=None, ambiguous=True, raw=raw)

    if has_comma or has_dot:
        sep = "," if has_comma else "."
        parts = cleaned.split(sep)
        trailing = parts[-1]
        if len(parts) == 2 and len(trailing) == 2:
            # Exactly two trailing digits: overwhelmingly a decimal
            # separator (cents), not a thousands group.
            normalized = cleaned.replace(sep, ".")
            try:
                return ParsedAmount(value=float(normalized), ambiguous=False, raw=raw)
            except ValueError:
                return ParsedAmount(value=None, ambiguous=True, raw=raw)
        if len(parts) == 2 and len(trailing) == 3:
            # Genuinely ambiguous: "1,234"/"1.234" could be a thousands
            # group (1234) or a decimal fraction (1.234). Do not guess.
            return ParsedAmount(value=None, ambiguous=True, raw=raw)
        if len(parts) == 2 and len(trailing) in (1, 4, 5, 6):
            # Very unusual as a thousands grouping; treat as decimal.
            normalized = cleaned.replace(sep, ".")
            try:
                return ParsedAmount(value=float(normalized), ambiguous=False, raw=raw)
            except ValueError:
                return ParsedAmount(value=None, ambiguous=True, raw=raw)
        if len(parts) > 2:
            # Multiple groups of the same separator with no decimal marker
            # visible: consistent with a pure thousands grouping (e.g.
            # "1,234,567" or "1.234.567").
            if all(len(p) == 3 for p in parts[1:]):
                normalized = cleaned.replace(sep, "")
                try:
                    return ParsedAmount(value=float(normalized), ambiguous=False, raw=raw)
                except ValueError:
                    return ParsedAmount(value=None, ambiguous=True, raw=raw)
            return ParsedAmount(value=None, ambiguous=True, raw=raw)

    try:
        return ParsedAmount(value=float(cleaned), ambiguous=False, raw=raw)
    except ValueError:
        return ParsedAmount(value=None, ambiguous=True, raw=raw)


def find_amounts(text: str) -> list[str]:
    """Extract plausible numeric amount substrings from a line of text."""
    return _NUMBER_RE.findall(text)

"""Currency detection from OCR text lines.

Matches currency symbols and ISO 4217 codes appearing as plain text.
Deliberately honest about ambiguity: some symbols map to more than one
currency (most notably "¥", used for both JPY and CNY) and, absent
another signal (an ISO code, a language/script hint, or an explicit
merchant locale), this module will not silently guess between them --
it reports the ambiguous candidate set instead of picking one.
"""

from __future__ import annotations

import re

from receiptlingua.extract.types import Evidence, ScalarField

# Symbol -> single unambiguous ISO 4217 code.
_UNAMBIGUOUS_SYMBOLS: dict[str, str] = {
    "$": "USD",  # Also used by several other USD-pegged/dollar currencies;
    # treated as USD by default since that is by far the most common
    # receipt-OCR case, but see _DOLLAR_CODE_HINTS below for overrides.
    "€": "EUR",
    "₹": "INR",
    "₨": "INR",  # Rs (older INR sign)
    "₦": "NGN",
    "£": "GBP",
    "₩": "KRW",
    "₱": "PHP",
    "₺": "TRY",
    "ر.س": "SAR",  # ر.س (Saudi riyal, common OCR rendering)
}

# Symbols that are genuinely ambiguous between multiple currencies without
# more context. Reported as a status="uncertain" candidate list rather than
# a guessed single value.
_AMBIGUOUS_SYMBOLS: dict[str, tuple[str, ...]] = {
    "¥": ("JPY", "CNY"),  # yen/yuan sign is shared
    "Rs": ("PKR", "INR", "LKR", "NPR"),  # Rs./Rs used by several rupee currencies
    "₨": ("INR", "PKR"),
}

# Other dollar-symbol currencies distinguishable only by an accompanying
# ISO code or explicit prefix (e.g. "AU$", "CA$", "PKR"). These are checked
# before falling back to the plain "$" -> USD default.
_DOLLAR_CODE_HINTS: dict[str, str] = {
    "AU$": "AUD",
    "A$": "AUD",
    "CA$": "CAD",
    "C$": "CAD",
    "NZ$": "NZD",
    "HK$": "HKD",
    "S$": "SGD",
}

_ISO_4217_CODES = (
    "USD",
    "EUR",
    "GBP",
    "INR",
    "PKR",
    "NGN",
    "JPY",
    "CNY",
    "KRW",
    "PHP",
    "TRY",
    "SAR",
    "AED",
    "AUD",
    "CAD",
    "NZD",
    "HKD",
    "SGD",
    "LKR",
    "NPR",
    "BDT",
    "ZAR",
    "BRL",
    "MXN",
    "IDR",
    "THB",
    "VND",
    "MYR",
    "EGP",
    "KES",
)
_ISO_CODE_RE = re.compile(r"\b(" + "|".join(_ISO_4217_CODES) + r")\b")


def detect_currency(lines: list[str]) -> ScalarField:
    """Detect a currency symbol/code across ``lines`` (already in reading order).

    Returns ``ok`` with a single ISO 4217 code when an unambiguous signal is
    found, ``uncertain`` with the candidate set when only an ambiguous
    symbol (e.g. ¥) is found, or ``missing`` when no currency signal
    appears at all.
    """
    dollar_hits: list[int] = []
    unambiguous_hits: dict[str, list[int]] = {}
    ambiguous_hits: dict[tuple[str, ...], list[int]] = {}
    iso_hits: dict[str, list[int]] = {}

    for idx, text in enumerate(lines):
        for hint, code in _DOLLAR_CODE_HINTS.items():
            if hint in text:
                unambiguous_hits.setdefault(code, []).append(idx)
        m = _ISO_CODE_RE.search(text)
        if m:
            iso_hits.setdefault(m.group(1), []).append(idx)
        for sym, codes in _AMBIGUOUS_SYMBOLS.items():
            if sym in text:
                ambiguous_hits.setdefault(codes, []).append(idx)
        for sym, code in _UNAMBIGUOUS_SYMBOLS.items():
            if sym in text:
                unambiguous_hits.setdefault(code, []).append(idx)
        if "$" in text and not any(h in text for h in _DOLLAR_CODE_HINTS):
            dollar_hits.append(idx)

    # An explicit ISO code is the strongest, least ambiguous signal.
    if iso_hits:
        code, line_idxs = max(iso_hits.items(), key=lambda kv: len(kv[1]))
        return ScalarField(
            status="ok",
            value=code,
            confidence=0.95,
            evidence=Evidence(text_line_indices=tuple(line_idxs)),
        )

    if unambiguous_hits:
        code, line_idxs = max(unambiguous_hits.items(), key=lambda kv: len(kv[1]))
        return ScalarField(
            status="ok",
            value=code,
            confidence=0.85,
            evidence=Evidence(text_line_indices=tuple(line_idxs)),
        )

    if dollar_hits:
        # Plain "$" with no country prefix: default to USD (most common
        # case in practice) but at reduced confidence since it truly could
        # be another dollar-pegged currency.
        return ScalarField(
            status="ok",
            value="USD",
            confidence=0.6,
            evidence=Evidence(text_line_indices=tuple(dollar_hits)),
        )

    if ambiguous_hits:
        codes, line_idxs = max(ambiguous_hits.items(), key=lambda kv: len(kv[1]))
        return ScalarField(
            status="uncertain",
            value={"candidates": list(codes)},
            confidence=0.3,
            evidence=Evidence(text_line_indices=tuple(line_idxs)),
        )

    return ScalarField.missing()

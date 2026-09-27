"""Multilingual keyword lists for locating labeled amount fields.

Only languages the project has real support for (per
python/src/receiptlingua/langid/data/language_matrix.json) are included,
and only where the translation is a standard, high-confidence receipt term
-- not a guess. Per the project's no-hallucination constraint: if a
language's correct receipt vocabulary is not confidently known here, its
list is left empty rather than shipping a wrong keyword.

Known gap: this covers English plus a small set of high-confidence
Arabic/Urdu terms. Tamil and most of the other 87 model_supported
languages are NOT covered here -- their standard receipt terminology was
not sourced with enough confidence for this pass, so they fall back to
number-proximity heuristics only (see amounts extraction). This should be
revisited with native-speaker review before the 171-185 benchmark
milestone, rather than expanded by guesswork here.
"""

from __future__ import annotations

# English is the baseline; Arabic/Urdu entries below are standard,
# widely-used receipt/invoice terms (not idiomatic guesses).
TOTAL_KEYWORDS: tuple[str, ...] = (
    "total", "grand total", "amount due", "balance due",
    "المجموع", "الإجمالي",  # Arabic: al-majmou' / al-ijmali
)

SUBTOTAL_KEYWORDS: tuple[str, ...] = (
    "subtotal", "sub-total", "sub total", "net amount",
)

TAX_KEYWORDS: tuple[str, ...] = (
    "tax", "vat", "gst", "hst", "sales tax",
    "الضريبة",  # Arabic: al-dariba (the tax)
)

DISCOUNT_KEYWORDS: tuple[str, ...] = (
    "discount", "coupon", "promo", "less", "savings",
    "خصم",  # Arabic: khasm (discount)
)

RECEIPT_NUMBER_KEYWORDS: tuple[str, ...] = (
    "receipt #", "receipt no", "receipt number", "invoice #", "invoice no",
    "invoice number", "order #", "order no", "transaction id", "trans id",
    "ref no", "reference no",
)

PAYMENT_METHOD_KEYWORDS: dict[str, tuple[str, ...]] = {
    # More specific brand names checked before the generic "card"/"credit"/
    # "debit" buckets, so e.g. "VISA" isn't swallowed by a generic match.
    "visa": ("visa",),
    "mastercard": ("mastercard", "master card"),
    "amex": ("amex", "american express"),
    "upi": ("upi",),
    "cheque": ("cheque", "check"),
    "cash": ("cash",),
    "credit_card": ("credit card", "credit"),
    "debit_card": ("debit card", "debit"),
    "card": ("card",),
}


def find_keyword_line(lines: list[str], keywords: tuple[str, ...]) -> int | None:
    """Return the index of the first line containing any keyword (case-insensitive)."""
    for idx, text in enumerate(lines):
        lowered = text.lower()
        for kw in keywords:
            if kw.lower() in lowered:
                return idx
    return None


def find_all_keyword_lines(lines: list[str], keywords: tuple[str, ...]) -> list[int]:
    """Return indices of all lines containing any keyword (case-insensitive)."""
    out = []
    for idx, text in enumerate(lines):
        lowered = text.lower()
        if any(kw.lower() in lowered for kw in keywords):
            out.append(idx)
    return out

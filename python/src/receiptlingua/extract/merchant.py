"""Merchant name extraction.

This is the weakest heuristic in this module: it assumes the merchant name
is one of the first few non-empty, non-noise lines at the top of the
receipt (in reconstructed reading order), which is a common but far from
universal layout convention. It is intentionally scored at low confidence
and marked ``uncertain`` (never ``ok``) so downstream consumers do not
over-trust it. Real accuracy numbers should come from the 171-185
benchmark milestone, not from this heuristic's confidence score.
"""

from __future__ import annotations

import re

from receiptlingua.extract.types import Evidence, ScalarField

_PURE_NUMBER_RE = re.compile(r"^[\d\s\-.,:/]+$")
_NOISE_PATTERNS = (
    re.compile(r"^(receipt|invoice|order|thank you|welcome|tel|phone|www\.|http)", re.IGNORECASE),
)
_MAX_LINES_CHECKED = 5
_MAX_CANDIDATE_LINES = 3


def extract_merchant(lines: list[str]) -> ScalarField:
    """Best-effort merchant name from the first few non-noise lines."""
    candidates: list[int] = []
    for idx, text in enumerate(lines[:_MAX_LINES_CHECKED]):
        stripped = text.strip()
        if not stripped:
            continue
        if _PURE_NUMBER_RE.match(stripped):
            continue
        if len(stripped) < 2:
            continue
        if any(p.search(stripped) for p in _NOISE_PATTERNS):
            continue
        candidates.append(idx)
        if len(candidates) >= _MAX_CANDIDATE_LINES:
            break

    if not candidates:
        return ScalarField.missing()

    value = " ".join(lines[i].strip() for i in candidates[:1])  # first candidate line only
    return ScalarField(
        status="uncertain",
        value=value,
        confidence=0.35,
        evidence=Evidence(text_line_indices=tuple(candidates[:1])),
    )

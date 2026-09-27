"""Receipt/invoice number extraction: keyword-anchored, English only for now.

See docs/COMMIT_PLAN.md 101-120 for why non-English keyword coverage is
deliberately left out here rather than guessed.
"""

from __future__ import annotations

import re

from receiptlingua.extract.keywords import RECEIPT_NUMBER_KEYWORDS
from receiptlingua.extract.types import Evidence, ScalarField

_VALUE_RE = re.compile(r"[:#]?\s*([A-Za-z0-9][A-Za-z0-9\-/]{2,})\s*$")


def extract_receipt_number(lines: list[str]) -> ScalarField:
    for idx, text in enumerate(lines):
        lowered = text.lower()
        for kw in RECEIPT_NUMBER_KEYWORDS:
            pos = lowered.find(kw.lower())
            if pos == -1:
                continue
            remainder = text[pos + len(kw) :]
            m = _VALUE_RE.search(remainder)
            if m:
                return ScalarField(
                    status="ok",
                    value=m.group(1),
                    confidence=0.8,
                    evidence=Evidence(text_line_indices=(idx,)),
                )
            # Keyword found but no parseable value on the same line: check
            # the next non-empty line before giving up on this keyword hit.
            if idx + 1 < len(lines) and lines[idx + 1].strip():
                m2 = _VALUE_RE.search(lines[idx + 1].strip())
                if m2:
                    return ScalarField(
                        status="ok",
                        value=m2.group(1),
                        confidence=0.7,
                        evidence=Evidence(text_line_indices=(idx, idx + 1)),
                    )
            return ScalarField(status="uncertain", evidence=Evidence(text_line_indices=(idx,)))
    return ScalarField.missing()

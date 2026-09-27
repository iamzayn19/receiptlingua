"""Payment method extraction via keyword matching."""

from __future__ import annotations

from receiptlingua.extract.keywords import PAYMENT_METHOD_KEYWORDS
from receiptlingua.extract.types import Evidence, ScalarField


def extract_payment_method(lines: list[str]) -> ScalarField:
    for idx, text in enumerate(lines):
        lowered = text.lower()
        for method, keywords in PAYMENT_METHOD_KEYWORDS.items():
            if any(kw in lowered for kw in keywords):
                return ScalarField(
                    status="ok",
                    value=method,
                    confidence=0.75,
                    evidence=Evidence(text_line_indices=(idx,)),
                )
    return ScalarField.missing()

"""Rule-based structured receipt-field extraction (milestone 101-120).

Deliberately v0/heuristic, not ML-based: a reasonable, honestly-scoped
choice for this milestone (see docs/COMMIT_PLAN.md). Every extracted value
carries a ``status`` (``ok``/``inferred_field``/``uncertain``/``missing``)
and, when a value is present, ``evidence`` linking back to the source
``text_lines`` -- raw OCR is never silently discarded, and fields that
cannot be confidently extracted are marked ``missing``/``uncertain`` rather
than guessed.
"""

from receiptlingua.extract.extractor import extract_fields
from receiptlingua.extract.types import Evidence, LineItem, ScalarField, StructuredFields

__all__ = [
    "Evidence",
    "LineItem",
    "ScalarField",
    "StructuredFields",
    "extract_fields",
]

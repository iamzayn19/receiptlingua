"""Keyword-anchored extraction of subtotal/tax/discount/total, with inference.

For each of subtotal/tax/discount/total: find a line matching that field's
keyword list, then parse the first amount found on that same line (falling
back to the next non-empty line, since some receipt layouts put the label
and value on separate lines). If no keyword line is found, or the amount on
it can't be confidently parsed, the field is ``missing``/``uncertain`` --
never a guess.

If ``total`` is missing but ``subtotal`` and ``tax`` are both present (and
``discounts``, if present), ``total`` is computed and marked
``inferred_field``, with evidence pointing at the subtotal/tax/discount
lines it was derived from -- not at a nonexistent total line. This is the
one place this module computes a value rather than only reading one.
"""

from __future__ import annotations

from receiptlingua.extract.amounts import find_amounts, parse_amount
from receiptlingua.extract.keywords import (
    DISCOUNT_KEYWORDS,
    SUBTOTAL_KEYWORDS,
    TAX_KEYWORDS,
    TOTAL_KEYWORDS,
)
from receiptlingua.extract.types import Evidence, ScalarField


def _amount_on_line_or_next(lines: list[str], idx: int) -> tuple[float | None, bool, int]:
    """Try to parse an amount from ``lines[idx]``, else the next non-empty line.

    Returns (value_or_None, ambiguous, line_index_used).
    """
    for candidate_idx in (idx, idx + 1):
        if candidate_idx >= len(lines):
            continue
        amounts = find_amounts(lines[candidate_idx])
        if not amounts:
            continue
        parsed = parse_amount(amounts[-1])  # last number on the line is usually the value
        return parsed.value, parsed.ambiguous, candidate_idx
    return None, False, idx


def _extract_labeled_amount(lines: list[str], keywords: tuple[str, ...]) -> ScalarField:
    from receiptlingua.extract.keywords import find_keyword_line

    idx = find_keyword_line(lines, keywords)
    if idx is None:
        return ScalarField.missing()

    value, ambiguous, used_idx = _amount_on_line_or_next(lines, idx)
    line_indices = tuple(sorted({idx, used_idx}))
    if value is None:
        if ambiguous:
            return ScalarField(status="uncertain", evidence=Evidence(text_line_indices=line_indices))
        return ScalarField(status="uncertain", evidence=Evidence(text_line_indices=(idx,)))
    if ambiguous:
        return ScalarField(status="uncertain", evidence=Evidence(text_line_indices=line_indices))
    return ScalarField(status="ok", value=value, confidence=0.8, evidence=Evidence(text_line_indices=line_indices))


def extract_subtotal(lines: list[str]) -> ScalarField:
    return _extract_labeled_amount(lines, SUBTOTAL_KEYWORDS)


def extract_tax(lines: list[str]) -> ScalarField:
    return _extract_labeled_amount(lines, TAX_KEYWORDS)


def extract_discount(lines: list[str]) -> ScalarField:
    return _extract_labeled_amount(lines, DISCOUNT_KEYWORDS)


def extract_total(lines: list[str]) -> ScalarField:
    return _extract_labeled_amount(lines, TOTAL_KEYWORDS)


def extract_amount_fields(lines: list[str]) -> dict[str, ScalarField]:
    """Extract subtotal/tax/discounts/total, inferring total when missing."""
    subtotal = extract_subtotal(lines)
    tax = extract_tax(lines)
    discount = extract_discount(lines)
    total = extract_total(lines)

    if total.status == "missing" and subtotal.status == "ok" and tax.status == "ok":
        discount_value = discount.value if discount.status == "ok" else 0.0
        inferred_value = subtotal.value + tax.value - discount_value
        evidence_indices: set[int] = set()
        if subtotal.evidence:
            evidence_indices.update(subtotal.evidence.text_line_indices)
        if tax.evidence:
            evidence_indices.update(tax.evidence.text_line_indices)
        if discount.status == "ok" and discount.evidence:
            evidence_indices.update(discount.evidence.text_line_indices)
        total = ScalarField(
            status="inferred_field",
            value=round(inferred_value, 2),
            confidence=0.6,
            evidence=Evidence(text_line_indices=tuple(sorted(evidence_indices))),
        )

    return {"subtotal": subtotal, "tax": tax, "discounts": discount, "total": total}

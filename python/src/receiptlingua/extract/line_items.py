"""Line-item table extraction: v0 best-effort, honestly scoped.

Known limitations (do not oversell this downstream):

- Works best on simple, single-column receipts where each item is one
  physical line formatted roughly as
  ``description ... quantity ... unit_price ... item_total``.
- It does not do real column-alignment detection across bbox x-coordinates
  for multi-line item descriptions or wrapped text; it treats each
  candidate line independently.
- It is not reliable on complex multi-currency tables, receipts with
  item descriptions spanning multiple lines, or tables using tab/column
  separators the OCR engine did not preserve as whitespace.
- Quantity is optional and defaults to 1 when a description+price pattern
  is found without a separate quantity token, since many receipts omit an
  explicit "1" for single-quantity items -- this is a deliberate
  simplification, not a detected value, so it is NOT given evidence of its
  own (it rides along with the line's overall status).

A line qualifies as a candidate item row when it contains at least two
numeric tokens, the last of which is treated as the item_total, and (when a
third numeric token exists before it) the first two are treated as
quantity and unit_price with a sanity check that qty * unit_price
approximately equals item_total (within rounding tolerance). Lines that
match total/subtotal/tax/discount keywords are excluded so summary rows
are never mistaken for item rows.
"""

from __future__ import annotations

from receiptlingua.extract.amounts import find_amounts, parse_amount
from receiptlingua.extract.keywords import (
    DISCOUNT_KEYWORDS,
    SUBTOTAL_KEYWORDS,
    TAX_KEYWORDS,
    TOTAL_KEYWORDS,
)
from receiptlingua.extract.types import Evidence, LineItem, ScalarField

_SUMMARY_KEYWORDS = TOTAL_KEYWORDS + SUBTOTAL_KEYWORDS + TAX_KEYWORDS + DISCOUNT_KEYWORDS


def _is_summary_line(text: str) -> bool:
    lowered = text.lower()
    return any(kw.lower() in lowered for kw in _SUMMARY_KEYWORDS)


def _description_before(text: str, first_number: str) -> str:
    pos = text.find(first_number)
    return text[:pos].strip() if pos > 0 else ""


def extract_line_items(lines: list[str]) -> list[LineItem]:
    items: list[LineItem] = []
    for idx, text in enumerate(lines):
        if not text.strip() or _is_summary_line(text):
            continue
        numbers = find_amounts(text)
        if len(numbers) < 2:
            continue

        parsed = [parse_amount(n) for n in numbers]
        if any(p.value is None for p in parsed):
            continue  # ambiguous/unparseable number on the row -- skip rather than guess

        description = _description_before(text, numbers[0])
        if not description:
            continue  # no leading description text -- likely not an item row

        item_total_field = ScalarField(status="ok", value=parsed[-1].value, confidence=0.6, evidence=Evidence(text_line_indices=(idx,)))
        description_field = ScalarField(status="ok", value=description, confidence=0.5, evidence=Evidence(text_line_indices=(idx,)))

        if len(parsed) >= 3:
            qty, unit_price, item_total = parsed[-3].value, parsed[-2].value, parsed[-1].value
            if abs(qty * unit_price - item_total) < 0.02:
                items.append(
                    LineItem(
                        status="ok",
                        description=description_field,
                        quantity=ScalarField(status="ok", value=qty, confidence=0.6, evidence=Evidence(text_line_indices=(idx,))),
                        unit_price=ScalarField(status="ok", value=unit_price, confidence=0.6, evidence=Evidence(text_line_indices=(idx,))),
                        item_total=item_total_field,
                        evidence=Evidence(text_line_indices=(idx,)),
                    )
                )
                continue

        # Two numbers only, or three that don't reconcile: treat as
        # description + item_total, quantity defaulted (not detected).
        unit_price = parsed[-2].value if len(parsed) >= 2 else None
        items.append(
            LineItem(
                status="uncertain" if len(parsed) >= 3 else "ok",
                description=description_field,
                quantity=ScalarField(status="inferred_field", value=1, confidence=0.3),
                unit_price=ScalarField(status="ok", value=unit_price, confidence=0.5, evidence=Evidence(text_line_indices=(idx,))) if unit_price is not None else None,
                item_total=item_total_field,
                evidence=Evidence(text_line_indices=(idx,)),
            )
        )
    return items

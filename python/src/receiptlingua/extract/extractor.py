"""Top-level structured-field extraction orchestrator.

``extract_fields`` takes OCR ``text_lines`` (as produced by
``receiptlingua.engines.types.EngineTextLine`` or any object exposing
``.text`` and ``.bbox``) plus each line's RTL flag, reconstructs reading
order, then runs every rule-based extractor over the reordered text.
Evidence indices returned by sub-extractors are expressed against the
*reordered* line list, so they are remapped back to indices into the
original ``text_lines`` array before being returned -- matching the
schema's ``evidence.text_line_indices`` contract, which indexes the
top-level (original-order) ``text_lines`` array.
"""

from __future__ import annotations

from receiptlingua.extract.amount_fields import extract_amount_fields
from receiptlingua.extract.currency import detect_currency
from receiptlingua.extract.dates import extract_date, extract_time
from receiptlingua.extract.line_items import extract_line_items
from receiptlingua.extract.merchant import extract_merchant
from receiptlingua.extract.payment_method import extract_payment_method
from receiptlingua.extract.reading_order import reconstruct_reading_order
from receiptlingua.extract.receipt_number import extract_receipt_number
from receiptlingua.extract.types import Evidence, LineItem, ScalarField, StructuredFields


def _remap_evidence(evidence: Evidence | None, order: list[int]) -> Evidence | None:
    if evidence is None:
        return None
    remapped = tuple(order[i] for i in evidence.text_line_indices)
    return Evidence(text_line_indices=remapped, word_indices=evidence.word_indices)


def _remap_scalar(field: ScalarField | None, order: list[int]) -> ScalarField | None:
    if field is None:
        return None
    return ScalarField(
        status=field.status,
        value=field.value,
        confidence=field.confidence,
        evidence=_remap_evidence(field.evidence, order),
    )


def _remap_line_item(item: LineItem, order: list[int]) -> LineItem:
    return LineItem(
        status=item.status,
        description=_remap_scalar(item.description, order),
        quantity=_remap_scalar(item.quantity, order),
        unit_price=_remap_scalar(item.unit_price, order),
        item_total=_remap_scalar(item.item_total, order),
        evidence=_remap_evidence(item.evidence, order),
    )


def extract_fields(text_lines: list, rtl_flags: list[bool] | None = None) -> StructuredFields:
    """Extract all structured receipt fields from OCR ``text_lines``.

    ``text_lines`` should be a list of objects with ``.text`` (str) and
    ``.bbox`` (object with ``.x``/``.y``/``.width``/``.height``) -- e.g.
    ``receiptlingua.engines.types.EngineTextLine``. ``rtl_flags[i]`` marks
    whether ``text_lines[i]`` is right-to-left script, typically derived
    from ``receiptlingua.langid`` per-line script tags.

    Returns a :class:`StructuredFields` whose every field's evidence
    indexes into the *original* ``text_lines`` order (matching the
    top-level response schema), regardless of the internal reading-order
    reconstruction used to run the extractors themselves.
    """
    order = reconstruct_reading_order(list(text_lines), rtl_flags)
    ordered_text = [text_lines[i].text for i in order]

    amount_fields = extract_amount_fields(ordered_text)
    line_items = extract_line_items(ordered_text)

    fields = StructuredFields(
        merchant=extract_merchant(ordered_text),
        merchant_address=ScalarField.missing(),
        date=extract_date(ordered_text),
        time=extract_time(ordered_text),
        currency=detect_currency(ordered_text),
        subtotal=amount_fields["subtotal"],
        tax=amount_fields["tax"],
        discounts=amount_fields["discounts"],
        total=amount_fields["total"],
        payment_method=extract_payment_method(ordered_text),
        receipt_number=extract_receipt_number(ordered_text),
        line_items=tuple(line_items),
    )

    return StructuredFields(
        merchant=_remap_scalar(fields.merchant, order),
        merchant_address=_remap_scalar(fields.merchant_address, order),
        date=_remap_scalar(fields.date, order),
        time=_remap_scalar(fields.time, order),
        currency=_remap_scalar(fields.currency, order),
        subtotal=_remap_scalar(fields.subtotal, order),
        tax=_remap_scalar(fields.tax, order),
        discounts=_remap_scalar(fields.discounts, order),
        total=_remap_scalar(fields.total, order),
        payment_method=_remap_scalar(fields.payment_method, order),
        receipt_number=_remap_scalar(fields.receipt_number, order),
        line_items=tuple(_remap_line_item(item, order) for item in fields.line_items),
    )

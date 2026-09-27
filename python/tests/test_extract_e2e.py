"""End-to-end extract_fields tests against hand-constructed fake OCR input.

These are unit tests against synthetic text_line data -- not accuracy
claims against real receipts (that's milestone 171-185).
"""

from __future__ import annotations

from receiptlingua.extract.extractor import extract_fields
from tests.extract_helpers import linear_lines, make_lines


def test_clean_english_receipt_clear_fields():
    lines = linear_lines(
        [
            "Corner Store",
            "2024-03-15 14:35",
            "Milk 2 1.50 3.00",
            "Subtotal 3.00",
            "Tax 0.30",
            "Total 3.30",
            "Paid by CASH",
        ]
    )
    fields = extract_fields(lines)
    assert fields.merchant.value == "Corner Store"
    assert fields.date.status == "ok" and fields.date.value == "2024-03-15"
    assert fields.time.status == "ok" and fields.time.value == "14:35:00"
    assert fields.total.status == "ok" and fields.total.value == 3.30
    assert fields.total.evidence.text_line_indices == (5,)
    assert fields.payment_method.value == "cash"
    assert len(fields.line_items) == 1


def test_missing_total_line_stays_missing_when_not_inferable():
    lines = linear_lines(["Corner Store", "Milk 3.00", "Paid by CASH"])
    fields = extract_fields(lines)
    assert fields.total.status == "missing"
    assert fields.total.value is None


def test_inferred_total_from_subtotal_and_tax():
    lines = linear_lines(["Corner Store", "Subtotal 10.00", "Tax 1.00", "Paid by CASH"])
    fields = extract_fields(lines)
    assert fields.total.status == "inferred_field"
    assert fields.total.value == 11.00
    # Evidence points at subtotal/tax lines (indices 1, 2), never a
    # nonexistent total line.
    assert set(fields.total.evidence.text_line_indices) == {1, 2}
    assert 3 not in fields.total.evidence.text_line_indices


def test_ambiguous_date_format_is_uncertain():
    lines = linear_lines(["Corner Store", "03/04/25", "Total 10.00"])
    fields = extract_fields(lines)
    assert fields.date.status == "uncertain"
    assert "candidates" in fields.date.value


def test_multi_currency_symbol_receipt():
    lines = linear_lines(["Corner Store", "Subtotal $10.00", "Total: 1500 PKR"])
    fields = extract_fields(lines)
    # Explicit ISO code beats the plain $ sign as the stronger signal.
    assert fields.currency.status == "ok"
    assert fields.currency.value == "PKR"


def test_evidence_indices_survive_reading_order_reconstruction():
    # Lines are supplied out of natural top-to-bottom order; evidence must
    # still point at the ORIGINAL (pre-reorder) text_lines indices.
    lines = make_lines(
        [
            ("Total 10.00", 10, 60),  # original index 0
            ("Corner Store", 10, 0),  # original index 1
            ("Subtotal 10.00", 10, 30),  # original index 2
        ]
    )
    fields = extract_fields(lines)
    assert fields.total.value == 10.00
    assert fields.total.evidence.text_line_indices == (0,)
    assert fields.merchant.evidence.text_line_indices == (1,)


def test_rtl_arabic_reading_order_reconstruction():
    # Two Arabic lines placed side by side in the same visual row; RTL means
    # the rightmost (higher x) line is logically first.
    lines = make_lines(
        [
            ("المتجر الركني", 100, 0),  # rightmost = first
            ("المجموع 100.00", 0, 0),
        ]
    )
    rtl_flags = [True, True]
    from receiptlingua.extract.reading_order import reconstruct_reading_order

    order = reconstruct_reading_order(list(lines), rtl_flags)
    assert order == [0, 1]

    fields = extract_fields(lines, rtl_flags)
    assert fields.total.status == "ok"
    assert fields.total.value == 100.00
    # Original index 1 held the amount line; evidence must reference it.
    assert fields.total.evidence.text_line_indices == (1,)


def test_line_items_table_multiple_rows():
    lines = linear_lines(
        [
            "Grocery Mart",
            "Milk 2 1.50 3.00",
            "Bread 1 2.50 2.50",
            "Eggs 3 0.50 1.50",
            "Butter 1 4.00 4.00",
            "Subtotal 11.00",
        ]
    )
    fields = extract_fields(lines)
    assert len(fields.line_items) == 4
    descriptions = [item.description.value for item in fields.line_items]
    assert descriptions == ["Milk", "Bread", "Eggs", "Butter"]
    totals = [item.item_total.value for item in fields.line_items]
    assert totals == [3.00, 2.50, 1.50, 4.00]

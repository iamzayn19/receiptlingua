"""Line-item table extraction tests."""

from __future__ import annotations

from receiptlingua.extract.line_items import extract_line_items


def test_extracts_multiple_item_rows_with_qty_price_total():
    lines = [
        "Store Name",
        "Milk 2 1.50 3.00",
        "Bread 1 2.50 2.50",
        "Eggs 3 0.50 1.50",
        "Subtotal 7.00",
    ]
    items = extract_line_items(lines)
    assert len(items) == 3
    milk = items[0]
    assert milk.status == "ok"
    assert milk.description.value == "Milk"
    assert milk.quantity.value == 2
    assert milk.unit_price.value == 1.50
    assert milk.item_total.value == 3.00
    assert milk.evidence.text_line_indices == (1,)


def test_summary_rows_are_not_treated_as_line_items():
    lines = ["Widget 2 5.00 10.00", "Subtotal 10.00", "Tax 1.00", "Total 11.00"]
    items = extract_line_items(lines)
    assert len(items) == 1
    assert items[0].description.value == "Widget"


def test_two_number_row_without_reconciling_qty_still_captured_as_uncertain_quantity():
    lines = ["Gift wrap 5.00"]
    items = extract_line_items(lines)
    assert len(items) == 1
    item = items[0]
    assert item.item_total.value == 5.00
    assert item.quantity.status == "inferred_field"
    assert item.quantity.value == 1

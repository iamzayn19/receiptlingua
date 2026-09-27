"""Subtotal/tax/discount/total extraction and inference tests."""

from __future__ import annotations

from receiptlingua.extract.amount_fields import extract_amount_fields


def test_all_fields_present_and_ok():
    lines = ["Subtotal 10.00", "Tax 1.00", "Total 11.00"]
    fields = extract_amount_fields(lines)
    assert fields["subtotal"].status == "ok" and fields["subtotal"].value == 10.00
    assert fields["tax"].status == "ok" and fields["tax"].value == 1.00
    assert fields["total"].status == "ok" and fields["total"].value == 11.00


def test_illegible_total_amount_is_uncertain_not_guessed():
    # Total keyword is present but the amount is illegible/unparseable --
    # must not silently guess a value.
    lines = ["Subtotal 10.00", "Tax 1.00", "Total: [illegible]"]
    fields = extract_amount_fields(lines)
    assert fields["total"].status == "uncertain"
    assert fields["total"].value is None


def test_total_inferred_from_subtotal_and_tax_when_missing():
    lines = ["Subtotal 10.00", "Tax 1.50", "Cash paid"]
    fields = extract_amount_fields(lines)
    total = fields["total"]
    assert total.status == "inferred_field"
    assert total.value == 11.50
    # Evidence points at the subtotal/tax lines, not at any (nonexistent) total line.
    assert set(total.evidence.text_line_indices) == {0, 1}


def test_total_inferred_accounts_for_discount():
    lines = ["Subtotal 100.00", "Discount 10.00", "Tax 9.00"]
    fields = extract_amount_fields(lines)
    total = fields["total"]
    assert total.status == "inferred_field"
    assert total.value == 99.00
    assert 0 in total.evidence.text_line_indices
    assert 1 in total.evidence.text_line_indices
    assert 2 in total.evidence.text_line_indices


def test_total_missing_when_no_keyword_and_no_inference_possible():
    # No total keyword and no subtotal/tax to infer from -- must stay missing.
    lines = ["Some item 5.00", "Cash paid"]
    fields = extract_amount_fields(lines)
    assert fields["total"].status == "missing"
    assert fields["total"].value is None


def test_no_keyword_lines_at_all_is_missing():
    fields = extract_amount_fields(["hello", "world"])
    for key in ("subtotal", "tax", "discounts", "total"):
        assert fields[key].status == "missing"

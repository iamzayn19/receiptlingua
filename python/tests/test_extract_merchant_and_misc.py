"""Merchant name, receipt number, and payment method extraction tests."""

from __future__ import annotations

from receiptlingua.extract.merchant import extract_merchant
from receiptlingua.extract.payment_method import extract_payment_method
from receiptlingua.extract.receipt_number import extract_receipt_number


def test_merchant_from_first_noise_free_line():
    lines = ["Corner Store", "123 Main St", "Total 10.00"]
    field = extract_merchant(lines)
    assert field.status == "uncertain"  # always uncertain -- weakest heuristic
    assert field.value == "Corner Store"
    assert field.evidence.text_line_indices == (0,)


def test_merchant_skips_boilerplate_and_numeric_lines():
    lines = ["Receipt #123", "42", "Fresh Grocers", "Total 5.00"]
    field = extract_merchant(lines)
    assert field.value == "Fresh Grocers"


def test_merchant_missing_when_all_lines_are_noise():
    lines = ["123", "456", "789"]
    field = extract_merchant(lines)
    assert field.status == "missing"


def test_receipt_number_keyword_and_pattern():
    field = extract_receipt_number(["Store", "Receipt #: A1234-5", "Total 5.00"])
    assert field.status == "ok"
    assert field.value == "A1234-5"


def test_receipt_number_missing_without_keyword():
    field = extract_receipt_number(["Store", "Total 5.00"])
    assert field.status == "missing"


def test_payment_method_cash():
    field = extract_payment_method(["Total 5.00", "Paid by CASH"])
    assert field.status == "ok"
    assert field.value == "cash"


def test_payment_method_visa():
    field = extract_payment_method(["Card: VISA **** 1234"])
    assert field.status == "ok"
    assert field.value == "visa"


def test_payment_method_missing():
    field = extract_payment_method(["Thank you for shopping"])
    assert field.status == "missing"

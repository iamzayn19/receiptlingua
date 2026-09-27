"""Currency detection tests."""

from __future__ import annotations

from receiptlingua.extract.currency import detect_currency


def test_detects_usd_dollar_sign():
    field = detect_currency(["Total $10.00"])
    assert field.status == "ok"
    assert field.value == "USD"


def test_detects_euro_symbol():
    field = detect_currency(["Total €10.00"])
    assert field.status == "ok"
    assert field.value == "EUR"


def test_detects_inr_symbol():
    field = detect_currency(["Total ₹500"])
    assert field.status == "ok"
    assert field.value == "INR"


def test_detects_explicit_iso_code():
    field = detect_currency(["Amount: 500 PKR"])
    assert field.status == "ok"
    assert field.value == "PKR"


def test_ambiguous_yen_yuan_symbol_is_uncertain():
    field = detect_currency(["Total ¥500"])
    assert field.status == "uncertain"
    assert set(field.value["candidates"]) == {"JPY", "CNY"}


def test_no_currency_signal_is_missing():
    field = detect_currency(["thank you for shopping"])
    assert field.status == "missing"


def test_multi_currency_symbol_receipt_prefers_iso_code():
    # A receipt showing both a plain $ and an explicit PKR code -- the ISO
    # code is the stronger, less ambiguous signal.
    field = detect_currency(["Subtotal $10", "Total: 1500 PKR"])
    assert field.status == "ok"
    assert field.value == "PKR"

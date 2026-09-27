"""Tests for the deterministic synthetic receipt generator."""

from __future__ import annotations

import pytest

from receiptlingua.synth.generator import SUPPORTED_LANGUAGES, generate_receipt


def test_supported_languages_nonempty():
    assert set(SUPPORTED_LANGUAGES) >= {"en", "ta", "ar"}


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
def test_generate_receipt_smoke(language):
    receipt = generate_receipt(language, seed=1)
    assert receipt.image.size[0] > 0 and receipt.image.size[1] > 0
    gt = receipt.ground_truth
    assert gt.merchant
    assert gt.total >= gt.subtotal
    assert len(gt.line_items) >= 3
    assert gt.full_text  # non-empty rendered text


def test_determinism_same_seed_same_output():
    r1 = generate_receipt("en", seed=123)
    r2 = generate_receipt("en", seed=123)
    assert r1.ground_truth.to_dict() == r2.ground_truth.to_dict()
    assert list(r1.image.getdata()) == list(r2.image.getdata())
    assert r1.image.size == r2.image.size


def test_different_seed_different_output():
    r1 = generate_receipt("en", seed=1)
    r2 = generate_receipt("en", seed=2)
    assert r1.ground_truth.to_dict() != r2.ground_truth.to_dict()


def test_unsupported_language_raises():
    with pytest.raises(ValueError):
        generate_receipt("zz", seed=1)


def test_ground_truth_amounts_consistent():
    receipt = generate_receipt("en", seed=7)
    gt = receipt.ground_truth
    computed_subtotal = round(sum(li.item_total for li in gt.line_items), 2)
    assert computed_subtotal == gt.subtotal
    assert round(gt.subtotal + gt.tax, 2) == gt.total


def test_save_roundtrip(tmp_path):
    receipt = generate_receipt("ta", seed=5)
    path = tmp_path / "gt.json"
    receipt.ground_truth.save(path)
    import json

    loaded = json.loads(path.read_text())
    assert loaded["merchant"] == receipt.ground_truth.merchant
    assert loaded["total"] == receipt.ground_truth.total

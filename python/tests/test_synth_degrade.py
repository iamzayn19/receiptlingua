"""Tests for the deterministic degradation functions."""

from __future__ import annotations

import pytest
from PIL import Image

from receiptlingua.synth.degrade import DEFERRED_DEGRADATIONS, DEGRADATIONS
from receiptlingua.synth.generator import SUPPORTED_LANGUAGES, generate_receipt


@pytest.fixture(scope="module")
def base_image():
    if "en" not in SUPPORTED_LANGUAGES:
        pytest.skip("no usable font found for 'en' on this machine")
    return generate_receipt("en", seed=99).image


@pytest.mark.parametrize("name", sorted(DEGRADATIONS.keys()))
def test_degradation_produces_valid_image(name, base_image):
    fn = DEGRADATIONS[name]
    out = fn(base_image, seed=42)
    assert isinstance(out, Image.Image)
    assert out.size[0] > 0 and out.size[1] > 0
    assert out.mode == "RGB"


@pytest.mark.parametrize("name", sorted(DEGRADATIONS.keys()))
def test_degradation_deterministic(name, base_image):
    fn = DEGRADATIONS[name]
    out1 = fn(base_image, seed=7)
    out2 = fn(base_image, seed=7)
    assert out1.size == out2.size
    assert list(out1.getdata()) == list(out2.getdata())


def test_clean_is_identity(base_image):
    out = DEGRADATIONS["clean"](base_image, seed=1)
    assert out.size == base_image.size
    assert list(out.getdata()) == list(base_image.getdata())


def test_different_seeds_generally_differ(base_image):
    # Skip degradations that are deterministic given fixed params (clean,
    # jpeg_compression) or whose randomized parameter range is narrow
    # enough that two draws can legitimately quantize to the exact same
    # pixels on a mostly-white receipt image (gaussian_blur's ksize is an
    # int(radius) bucket; perspective_warp's small pixel-level jitter can
    # round-trip identically through PERSPECTIVE resampling on white
    # background) -- determinism (same seed -> same output) is what
    # matters and is covered by test_degradation_deterministic above.
    for name, fn in DEGRADATIONS.items():
        if name in ("clean", "jpeg_compression", "gaussian_blur", "perspective_warp"):
            continue
        out1 = fn(base_image, seed=1)
        out2 = fn(base_image, seed=999999)
        assert out1.size != out2.size or list(out1.getdata()) != list(out2.getdata()), name


def test_deferred_degradations_documented_not_claimed():
    # These must never silently appear as "working" in the real registry.
    assert "tear_missing_section" in DEFERRED_DEGRADATIONS
    assert "curved_page_dewarp" in DEFERRED_DEGRADATIONS
    for name in DEFERRED_DEGRADATIONS:
        assert name not in DEGRADATIONS

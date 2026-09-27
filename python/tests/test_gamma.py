from pathlib import Path

import numpy as np
import pytest

from receiptlingua.pipeline.preprocess import gamma, loading

FIXTURES = Path(__file__).parent / "fixtures"


def test_gamma_greater_than_one_brightens_dark_fixture():
    result = loading.load_image(FIXTURES / "receipt_dark.png")
    corrected = gamma.adjust_gamma(result.image, 2.5)
    assert corrected.mean() > np.asarray(result.image)[:, :, 0].mean()


def test_gamma_of_one_is_noop():
    result = loading.load_image(FIXTURES / "receipt_clean.png")
    from receiptlingua.pipeline.preprocess.grayscale import to_grayscale

    gray = to_grayscale(result.image)
    out = gamma.adjust_gamma(result.image, 1.0)
    assert np.array_equal(out, gray)


def test_invalid_gamma_raises():
    result = loading.load_image(FIXTURES / "receipt_clean.png")
    with pytest.raises(ValueError):
        gamma.adjust_gamma(result.image, 0)
    with pytest.raises(ValueError):
        gamma.adjust_gamma(result.image, -1.0)


def test_auto_gamma_brightens_dark_image_toward_target():
    result = loading.load_image(FIXTURES / "receipt_dark.png")
    before_mean = np.asarray(result.image)[:, :, 0].mean()
    corrected = gamma.auto_gamma_correct(result.image)
    after_mean = float(corrected.mean())
    assert after_mean > before_mean


def test_estimate_gamma_is_one_for_blank_or_saturated_image():
    black = np.zeros((10, 10), dtype=np.uint8)
    white = np.full((10, 10), 255, dtype=np.uint8)
    assert gamma.estimate_gamma(black) == 1.0
    assert gamma.estimate_gamma(white) == 1.0


def test_estimate_gamma_clamped_to_sane_range():
    very_dark = np.full((10, 10), 1, dtype=np.uint8)
    g = gamma.estimate_gamma(very_dark)
    assert 0.2 <= g <= 5.0

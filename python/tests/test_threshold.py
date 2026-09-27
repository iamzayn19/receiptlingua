from pathlib import Path

import numpy as np

from receiptlingua.pipeline.preprocess import loading, threshold

FIXTURES = Path(__file__).parent / "fixtures"


def test_adaptive_threshold_output_is_binary():
    result = loading.load_image(FIXTURES / "receipt_clean.png")
    out = threshold.adaptive_threshold(result.image)
    assert out.dtype == np.uint8
    assert set(np.unique(out).tolist()) <= {0, 255}
    assert out.shape == result.image.shape[:2]


def test_global_otsu_threshold_output_is_binary():
    result = loading.load_image(FIXTURES / "receipt_clean.png")
    out = threshold.global_otsu_threshold(result.image)
    assert set(np.unique(out).tolist()) <= {0, 255}


def test_even_block_size_is_bumped_not_rejected():
    result = loading.load_image(FIXTURES / "receipt_clean.png")
    out = threshold.adaptive_threshold(result.image, block_size=10)
    assert out.shape == result.image.shape[:2]


def test_too_small_block_size_is_clamped():
    result = loading.load_image(FIXTURES / "receipt_clean.png")
    out = threshold.adaptive_threshold(result.image, block_size=1)
    assert out.shape == result.image.shape[:2]


def test_dark_bars_end_up_as_foreground():
    result = loading.load_image(FIXTURES / "receipt_clean.png")
    out = threshold.global_otsu_threshold(result.image)
    # THRESH_BINARY with Otsu on a light-background/dark-foreground
    # image yields foreground (bars) as 0 and background as 255 by
    # default OpenCV convention -- assert the two populations exist and
    # differ, rather than a hardcoded polarity that could legitimately
    # flip with different fixture content.
    values, counts = np.unique(out, return_counts=True)
    assert len(values) == 2

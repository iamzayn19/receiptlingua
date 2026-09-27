from pathlib import Path

import cv2
import numpy as np

from receiptlingua.pipeline.preprocess import loading, sharpen

FIXTURES = Path(__file__).parent / "fixtures"


def _edge_strength(gray: np.ndarray) -> float:
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    return float(lap.var())


def test_zero_amount_is_unchanged_grayscale():
    result = loading.load_image(FIXTURES / "receipt_clean.png")
    from receiptlingua.pipeline.preprocess.grayscale import to_grayscale

    gray = to_grayscale(result.image)
    out = sharpen.unsharp_mask(result.image, amount=0.0)
    assert np.array_equal(out, gray)


def test_sharpening_increases_edge_strength_on_blurred_input():
    result = loading.load_image(FIXTURES / "receipt_clean.png")
    from receiptlingua.pipeline.preprocess.grayscale import to_grayscale

    gray = to_grayscale(result.image)
    blurred = cv2.GaussianBlur(gray, (0, 0), sigmaX=2.0)

    before = _edge_strength(blurred)
    sharpened = sharpen.unsharp_mask(blurred, amount=2.0)
    after = _edge_strength(sharpened)

    assert after > before


def test_output_shape_and_dtype():
    result = loading.load_image(FIXTURES / "receipt_clean.png")
    out = sharpen.unsharp_mask(result.image)
    assert out.shape == result.image.shape[:2]
    assert out.dtype == np.uint8

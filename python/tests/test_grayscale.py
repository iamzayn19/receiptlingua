from pathlib import Path

import numpy as np
import pytest

from receiptlingua.pipeline.preprocess import grayscale, loading

FIXTURES = Path(__file__).parent / "fixtures"


def test_rgb_image_converts_to_2d_uint8():
    result = loading.load_image(FIXTURES / "receipt_clean.png")
    gray = grayscale.to_grayscale(result.image)
    assert gray.ndim == 2
    assert gray.dtype == np.uint8
    assert gray.shape == result.image.shape[:2]


def test_already_grayscale_passes_through():
    arr = np.random.default_rng(0).integers(0, 255, size=(10, 10), dtype=np.uint8)
    gray = grayscale.to_grayscale(arr)
    assert np.array_equal(gray, arr)


def test_single_channel_3d_array():
    arr = np.random.default_rng(0).integers(0, 255, size=(10, 10, 1), dtype=np.uint8)
    gray = grayscale.to_grayscale(arr)
    assert gray.shape == (10, 10)


def test_rgba_image_converts():
    arr = np.zeros((10, 10, 4), dtype=np.uint8)
    arr[..., 3] = 255
    gray = grayscale.to_grayscale(arr)
    assert gray.shape == (10, 10)
    assert gray.dtype == np.uint8


def test_unsupported_shape_raises():
    with pytest.raises(ValueError):
        grayscale.to_grayscale(np.zeros((5, 5, 2), dtype=np.uint8))

    with pytest.raises(ValueError):
        grayscale.to_grayscale(np.zeros((5,), dtype=np.uint8))


def test_grayscale_preserves_contrast_ordering():
    # A white background with a black bar should stay darker in the bar
    # after conversion (sanity check that channels aren't scrambled).
    result = loading.load_image(FIXTURES / "receipt_clean.png")
    gray = grayscale.to_grayscale(result.image)
    assert gray.min() < 50
    assert gray.max() > 200

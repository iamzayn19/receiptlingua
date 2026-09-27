from pathlib import Path

import numpy as np

from receiptlingua.pipeline.preprocess import clahe, loading

FIXTURES = Path(__file__).parent / "fixtures"


def test_output_is_grayscale_uint8():
    result = loading.load_image(FIXTURES / "receipt_low_contrast.png")
    out = clahe.apply_clahe(result.image)
    assert out.ndim == 2
    assert out.dtype == np.uint8
    assert out.shape == result.image.shape[:2]


def test_increases_contrast_on_low_contrast_fixture():
    result = loading.load_image(FIXTURES / "receipt_low_contrast.png")
    before_std = np.asarray(result.image).astype(np.float32).std()

    enhanced = clahe.apply_clahe(result.image)
    after_std = enhanced.astype(np.float32).std()

    assert after_std > before_std


def test_preserves_shape_on_already_grayscale_input():
    arr = np.random.default_rng(0).integers(50, 200, size=(30, 30), dtype=np.uint8)
    out = clahe.apply_clahe(arr)
    assert out.shape == arr.shape


def test_custom_clip_limit_and_tile_size_accepted():
    result = loading.load_image(FIXTURES / "receipt_clean.png")
    out = clahe.apply_clahe(result.image, clip_limit=4.0, tile_grid_size=(4, 4))
    assert out.shape == result.image.shape[:2]

from pathlib import Path

import numpy as np

from receiptlingua.pipeline.preprocess import denoise, loading

FIXTURES = Path(__file__).parent / "fixtures"


def _noise_estimate(gray: np.ndarray) -> float:
    """Rough noise proxy: mean absolute Laplacian response."""
    import cv2

    lap = cv2.Laplacian(gray, cv2.CV_64F)
    return float(np.mean(np.abs(lap)))


def test_denoise_fast_reduces_noise_on_noisy_fixture():
    result = loading.load_image(FIXTURES / "receipt_noisy.png")
    before = _noise_estimate(np.asarray(result.image)[:, :, 0])
    denoised = denoise.denoise_fast(result.image)
    after = _noise_estimate(denoised)
    assert after < before


def test_denoise_accurate_reduces_noise_on_noisy_fixture():
    result = loading.load_image(FIXTURES / "receipt_noisy.png")
    before = _noise_estimate(np.asarray(result.image)[:, :, 0])
    denoised = denoise.denoise_accurate(result.image)
    after = _noise_estimate(denoised)
    assert after < before


def test_denoise_fast_output_shape_and_dtype():
    result = loading.load_image(FIXTURES / "receipt_clean.png")
    out = denoise.denoise_fast(result.image)
    assert out.shape == result.image.shape[:2]
    assert out.dtype == np.uint8


def test_denoise_fast_even_kernel_size_is_bumped():
    result = loading.load_image(FIXTURES / "receipt_clean.png")
    out = denoise.denoise_fast(result.image, kernel_size=4)
    assert out.shape == result.image.shape[:2]


def test_denoise_accurate_output_shape_and_dtype():
    result = loading.load_image(FIXTURES / "receipt_clean.png")
    out = denoise.denoise_accurate(result.image)
    assert out.shape == result.image.shape[:2]
    assert out.dtype == np.uint8

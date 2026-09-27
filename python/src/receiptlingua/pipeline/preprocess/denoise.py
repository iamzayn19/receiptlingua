"""Denoising.

Two tiers: a cheap median-blur denoise for the fast path, and a
slower-but-stronger non-local-means denoise for the accurate path when
the quality scorer flags a noisy image.
"""

from __future__ import annotations

import cv2
import numpy as np

from receiptlingua.pipeline.preprocess.grayscale import to_grayscale


def denoise_fast(image: np.ndarray, *, kernel_size: int = 3) -> np.ndarray:
    """Cheap median-filter denoise; good for light salt-and-pepper style noise."""
    gray = to_grayscale(image)
    if kernel_size < 3:
        kernel_size = 3
    if kernel_size % 2 == 0:
        kernel_size += 1
    return cv2.medianBlur(gray, kernel_size)


def denoise_accurate(
    image: np.ndarray,
    *,
    h: float = 10.0,
    template_window_size: int = 7,
    search_window_size: int = 21,
) -> np.ndarray:
    """Stronger non-local-means denoise; more expensive, better detail preservation."""
    gray = to_grayscale(image)
    return cv2.fastNlMeansDenoising(
        gray,
        h=h,
        templateWindowSize=template_window_size,
        searchWindowSize=search_window_size,
    )

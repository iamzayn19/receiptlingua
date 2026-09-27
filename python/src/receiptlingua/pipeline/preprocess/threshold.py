"""Adaptive thresholding.

Binarizes a grayscale image using a locally-adaptive threshold (Gaussian
mean of a neighborhood), which handles uneven illumination across a
receipt photo better than a single global threshold.
"""

from __future__ import annotations

import cv2
import numpy as np

from receiptlingua.pipeline.preprocess.grayscale import to_grayscale

DEFAULT_BLOCK_SIZE = 25
DEFAULT_C = 10


def adaptive_threshold(
    image: np.ndarray,
    *,
    block_size: int = DEFAULT_BLOCK_SIZE,
    c: int = DEFAULT_C,
) -> np.ndarray:
    """Binarize an image (dark text on light background) into a 0/255 mask.

    ``block_size`` must be odd and >= 3; even values are bumped up by 1
    to satisfy OpenCV's requirement rather than raising, since callers
    picking a block size from a heuristic shouldn't need to know this
    OpenCV quirk.
    """
    gray = to_grayscale(image)

    if block_size < 3:
        block_size = 3
    if block_size % 2 == 0:
        block_size += 1

    return cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        block_size,
        c,
    )


def global_otsu_threshold(image: np.ndarray) -> np.ndarray:
    """Binarize using a single global Otsu threshold (cheaper, less robust to uneven lighting)."""
    gray = to_grayscale(image)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary

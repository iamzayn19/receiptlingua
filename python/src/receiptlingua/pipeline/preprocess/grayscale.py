"""Grayscale normalization.

Most downstream OCR-relevant stages (thresholding, CLAHE, blur/contrast
scoring) operate on a single luminance channel. This module converts
RGB/RGBA/already-grayscale arrays into a consistent single-channel
uint8 representation.
"""

from __future__ import annotations

import cv2
import numpy as np


def to_grayscale(image: np.ndarray) -> np.ndarray:
    """Convert an image array to single-channel uint8 grayscale.

    Accepts (H, W) grayscale, (H, W, 1), (H, W, 3) RGB, or (H, W, 4)
    RGBA arrays. Raises ``ValueError`` for anything else, since an
    unrecognized shape indicates a bug upstream rather than bad input
    data (that should already have been rejected by loading.py).
    """
    if image.ndim == 2:
        gray = image
    elif image.ndim == 3 and image.shape[2] == 1:
        gray = image[:, :, 0]
    elif image.ndim == 3 and image.shape[2] == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    elif image.ndim == 3 and image.shape[2] == 4:
        gray = cv2.cvtColor(image, cv2.COLOR_RGBA2GRAY)
    else:
        raise ValueError(f"Unsupported image shape for grayscale conversion: {image.shape}")

    if gray.dtype != np.uint8:
        gray = np.clip(gray, 0, 255).astype(np.uint8)
    return gray

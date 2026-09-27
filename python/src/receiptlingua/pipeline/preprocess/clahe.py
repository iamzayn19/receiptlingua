"""CLAHE (Contrast Limited Adaptive Histogram Equalization).

Improves local contrast on low-contrast or unevenly-lit receipt photos
without over-amplifying noise the way global histogram equalization
would.
"""

from __future__ import annotations

import cv2
import numpy as np

from receiptlingua.pipeline.preprocess.grayscale import to_grayscale

DEFAULT_CLIP_LIMIT = 2.0
DEFAULT_TILE_GRID_SIZE = (8, 8)


def apply_clahe(
    image: np.ndarray,
    *,
    clip_limit: float = DEFAULT_CLIP_LIMIT,
    tile_grid_size: tuple[int, int] = DEFAULT_TILE_GRID_SIZE,
) -> np.ndarray:
    """Apply CLAHE to an image, converting to grayscale first if needed.

    Always returns a single-channel uint8 array; callers that need the
    result stacked back into RGB should do so explicitly.
    """
    gray = to_grayscale(image)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    return clahe.apply(gray)

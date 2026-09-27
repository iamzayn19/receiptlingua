"""Sharpening.

Unsharp-mask style sharpening to recover edge definition lost to
denoising or slight camera blur, applied conservatively so it does not
reintroduce noise.
"""

from __future__ import annotations

import cv2
import numpy as np

from receiptlingua.pipeline.preprocess.grayscale import to_grayscale

DEFAULT_AMOUNT = 1.0
DEFAULT_BLUR_SIGMA = 1.0


def unsharp_mask(
    image: np.ndarray,
    *,
    amount: float = DEFAULT_AMOUNT,
    blur_sigma: float = DEFAULT_BLUR_SIGMA,
) -> np.ndarray:
    """Sharpen via unsharp masking: original + amount * (original - blurred).

    ``amount`` of 0 returns the (grayscale-converted) image unchanged;
    higher values sharpen more aggressively.
    """
    gray = to_grayscale(image).astype(np.float32)
    blurred = cv2.GaussianBlur(gray, (0, 0), sigmaX=blur_sigma)
    sharpened = gray + amount * (gray - blurred)
    return np.clip(sharpened, 0, 255).astype(np.uint8)

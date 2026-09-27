"""Gamma / illumination correction.

Corrects overly dark or overly bright images via gamma adjustment, and
offers an auto-gamma helper that picks a correction factor from the
image's mean brightness so callers don't need to hand-tune it per
image.
"""

from __future__ import annotations

import numpy as np

from receiptlingua.pipeline.preprocess.grayscale import to_grayscale

# Target mean brightness (0-255) that auto-gamma aims for.
TARGET_MEAN_BRIGHTNESS = 150.0


def adjust_gamma(image: np.ndarray, gamma: float) -> np.ndarray:
    """Apply gamma correction: output = 255 * (input / 255) ** (1 / gamma).

    ``gamma`` > 1 brightens a dark image; ``gamma`` < 1 darkens a bright
    one. ``gamma`` == 1 is a no-op.
    """
    if gamma <= 0:
        raise ValueError("gamma must be positive")

    gray = to_grayscale(image)
    if gamma == 1.0:
        return gray

    normalized = gray.astype(np.float64) / 255.0
    corrected = np.power(normalized, 1.0 / gamma)
    return np.clip(corrected * 255.0, 0, 255).astype(np.uint8)


def estimate_gamma(image: np.ndarray, *, target_mean: float = TARGET_MEAN_BRIGHTNESS) -> float:
    """Estimate a gamma value that brings the image's mean brightness toward ``target_mean``."""
    gray = to_grayscale(image)
    mean_brightness = float(gray.mean())

    if mean_brightness <= 0 or mean_brightness >= 255:
        return 1.0

    # Solve for gamma such that target_mean/255 == (mean/255)**(1/gamma).
    log_ratio = np.log(target_mean / 255.0) / np.log(mean_brightness / 255.0)
    gamma = 1.0 / log_ratio if log_ratio != 0 else 1.0

    # Clamp to a sane range; extreme corrections usually indicate a
    # near-blank or fully saturated image rather than a useful signal.
    return float(np.clip(gamma, 0.2, 5.0))


def auto_gamma_correct(
    image: np.ndarray, *, target_mean: float = TARGET_MEAN_BRIGHTNESS
) -> np.ndarray:
    """Apply gamma correction using an automatically estimated gamma value."""
    gamma = estimate_gamma(image, target_mean=target_mean)
    return adjust_gamma(image, gamma)

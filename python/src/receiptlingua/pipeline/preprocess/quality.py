"""Lightweight image-quality heuristic scorer.

Computes cheap blur/contrast/brightness metrics used to decide whether
a fast preprocessing pass is sufficient or whether the pipeline should
escalate to more expensive candidates/passes (see ``orchestrator.py``
and the fast/accurate/auto mode selection in the OCR engine layer).
This is deliberately not a learned quality model -- it is a fast,
explainable proxy meant to gate escalation cheaply, not to score OCR
accuracy directly.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from receiptlingua.pipeline.preprocess.grayscale import to_grayscale

# Below this variance-of-Laplacian value, an image is considered blurry.
BLUR_VARIANCE_THRESHOLD = 100.0

# Below this standard deviation of pixel intensities, an image is
# considered low-contrast.
CONTRAST_STD_THRESHOLD = 40.0

# Mean brightness outside [MIN, MAX] is considered under/over-exposed.
BRIGHTNESS_MIN = 60.0
BRIGHTNESS_MAX = 225.0


@dataclass(frozen=True)
class QualityScore:
    blur_score: float  # variance of Laplacian; higher = sharper
    contrast_score: float  # stddev of intensities; higher = more contrast
    brightness_score: float  # mean intensity, 0-255
    is_blurry: bool
    is_low_contrast: bool
    is_poorly_lit: bool

    @property
    def needs_accurate_mode(self) -> bool:
        """Whether any signal suggests the fast preprocessing path is insufficient."""
        return self.is_blurry or self.is_low_contrast or self.is_poorly_lit


def compute_blur_score(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def compute_contrast_score(gray: np.ndarray) -> float:
    return float(gray.std())


def compute_brightness_score(gray: np.ndarray) -> float:
    return float(gray.mean())


def score_quality(
    image: np.ndarray,
    *,
    blur_threshold: float = BLUR_VARIANCE_THRESHOLD,
    contrast_threshold: float = CONTRAST_STD_THRESHOLD,
    brightness_min: float = BRIGHTNESS_MIN,
    brightness_max: float = BRIGHTNESS_MAX,
) -> QualityScore:
    """Compute blur/contrast/brightness heuristics for an image."""
    gray = to_grayscale(image)

    blur = compute_blur_score(gray)
    contrast = compute_contrast_score(gray)
    brightness = compute_brightness_score(gray)

    return QualityScore(
        blur_score=blur,
        contrast_score=contrast,
        brightness_score=brightness,
        is_blurry=blur < blur_threshold,
        is_low_contrast=contrast < contrast_threshold,
        is_poorly_lit=brightness < brightness_min or brightness > brightness_max,
    )

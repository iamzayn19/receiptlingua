"""Deskew: rotation angle estimation and correction.

Estimates small rotational skew (typically a few degrees, from a
slightly angled camera shot or scan) via the minimum-area bounding
rectangle of dark foreground pixels, and rotates the image to correct
it. This is a lightweight heuristic, not a full text-line-angle model;
see :mod:`perspective` for full quadrilateral correction of more
extreme distortion.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from receiptlingua.pipeline.preprocess.grayscale import to_grayscale

# Skew estimation is only meaningful for small angles; beyond this we
# assume the minAreaRect locked onto noise rather than real skew, and
# report zero rather than a wild correction.
MAX_PLAUSIBLE_SKEW_DEGREES = 30.0


@dataclass(frozen=True)
class DeskewResult:
    angle_degrees: float
    image: np.ndarray


def estimate_skew_angle(image: np.ndarray) -> float:
    """Estimate the skew angle (degrees) of the dominant foreground content.

    Positive angles mean the content is rotated counter-clockwise and
    needs a clockwise correction (as applied by :func:`deskew`), and
    vice versa. Returns 0.0 for blank or near-blank images where no
    reliable estimate can be made.
    """
    gray = to_grayscale(image)

    # Binarize: assume text/content is darker than the background.
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    coords = np.column_stack(np.where(binary > 0))
    if coords.shape[0] < 10:
        return 0.0

    rect = cv2.minAreaRect(coords.astype(np.float32))
    angle = rect[-1]

    # cv2.minAreaRect returns angle in [-90, 0); normalize to a
    # human-friendly small rotation.
    if angle < -45:
        angle = 90 + angle

    if abs(angle) > MAX_PLAUSIBLE_SKEW_DEGREES:
        return 0.0

    return float(angle)


def rotate_image(image: np.ndarray, angle_degrees: float) -> np.ndarray:
    """Rotate an image about its center by the given angle, expanding the canvas to fit."""
    if angle_degrees == 0.0:
        return image

    height, width = image.shape[:2]
    center = (width / 2, height / 2)
    matrix = cv2.getRotationMatrix2D(center, angle_degrees, 1.0)

    cos = abs(matrix[0, 0])
    sin = abs(matrix[0, 1])
    new_width = int((height * sin) + (width * cos))
    new_height = int((height * cos) + (width * sin))

    matrix[0, 2] += (new_width / 2) - center[0]
    matrix[1, 2] += (new_height / 2) - center[1]

    border_value = 255 if image.ndim == 2 else (255,) * image.shape[2]
    return cv2.warpAffine(
        image,
        matrix,
        (new_width, new_height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=border_value,
    )


def deskew(image: np.ndarray) -> DeskewResult:
    """Estimate skew and return the corrected image alongside the angle used.

    ``angle_degrees`` is the estimated skew of the *input* image;
    ``rotate_image`` is applied with the opposite sign to correct it.
    """
    angle = estimate_skew_angle(image)
    corrected = rotate_image(image, -angle)
    return DeskewResult(angle_degrees=angle, image=corrected)

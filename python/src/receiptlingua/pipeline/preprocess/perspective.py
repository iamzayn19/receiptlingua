"""Perspective / document-boundary detection and correction (v0 heuristic).

This is a deliberately simplified, best-effort approach for v0: it
looks for the largest quadrilateral contour in an edge map and, if
found, warps it to a rectangle. It works well for photos with strong
contrast between the receipt and its background (e.g. a receipt on a
dark desk) and is expected to under-perform on cluttered or low-
contrast backgrounds.

A future ADR should evaluate whether a trained document-boundary
segmentation model is warranted once real-world receipt photos are
available to benchmark against -- see the design note in
docs/adr/ (to be filed) referenced from ARCHITECTURE.md's pipeline
description. For now, callers should treat this stage as optional and
skip it when detection confidence is low (``BoundaryResult.found`` is
False), running OCR on the original (deskewed) image instead.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from receiptlingua.pipeline.preprocess.grayscale import to_grayscale

# A detected quadrilateral covering less than this fraction of the
# total image area is treated as noise, not a document boundary.
MIN_AREA_FRACTION = 0.2


@dataclass(frozen=True)
class BoundaryResult:
    found: bool
    corners: np.ndarray | None  # shape (4, 2), float32, order: TL, TR, BR, BL


def _order_corners(pts: np.ndarray) -> np.ndarray:
    """Order 4 points as top-left, top-right, bottom-right, bottom-left."""
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).flatten()
    rect[0] = pts[np.argmin(s)]  # top-left: smallest x+y
    rect[2] = pts[np.argmax(s)]  # bottom-right: largest x+y
    rect[1] = pts[np.argmin(diff)]  # top-right: smallest y-x
    rect[3] = pts[np.argmax(diff)]  # bottom-left: largest y-x
    return rect


def detect_document_boundary(image: np.ndarray) -> BoundaryResult:
    """Best-effort detection of a quadrilateral document boundary.

    Returns ``BoundaryResult(found=False, corners=None)`` when no
    plausible quadrilateral is found, rather than guessing.
    """
    gray = to_grayscale(image)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return BoundaryResult(found=False, corners=None)

    image_area = gray.shape[0] * gray.shape[1]
    best_quad: np.ndarray | None = None
    best_area = 0.0

    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:10]:
        area = cv2.contourArea(contour)
        if area < MIN_AREA_FRACTION * image_area:
            continue
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approx) == 4 and area > best_area:
            best_quad = approx.reshape(4, 2).astype(np.float32)
            best_area = area

    if best_quad is None:
        return BoundaryResult(found=False, corners=None)

    return BoundaryResult(found=True, corners=_order_corners(best_quad))


def correct_perspective(image: np.ndarray, corners: np.ndarray) -> np.ndarray:
    """Warp the quadrilateral defined by ``corners`` (TL, TR, BR, BL) to a rectangle."""
    (tl, tr, br, bl) = corners

    width_top = np.linalg.norm(tr - tl)
    width_bottom = np.linalg.norm(br - bl)
    height_left = np.linalg.norm(bl - tl)
    height_right = np.linalg.norm(br - tr)

    max_width = max(int(width_top), int(width_bottom), 1)
    max_height = max(int(height_left), int(height_right), 1)

    destination = np.array(
        [[0, 0], [max_width - 1, 0], [max_width - 1, max_height - 1], [0, max_height - 1]],
        dtype=np.float32,
    )

    matrix = cv2.getPerspectiveTransform(corners, destination)
    border_value = 255 if image.ndim == 2 else (255,) * image.shape[2]
    return cv2.warpPerspective(
        image,
        matrix,
        (max_width, max_height),
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=border_value,
    )


def detect_and_correct(image: np.ndarray) -> np.ndarray:
    """Detect a document boundary and correct it; returns the original image if none is found."""
    result = detect_document_boundary(image)
    if not result.found:
        return image
    return correct_perspective(image, result.corners)

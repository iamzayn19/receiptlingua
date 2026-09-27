"""EXIF orientation normalization.

Cameras/phones often store images "as captured" plus an EXIF
``Orientation`` tag describing the rotation/flip needed to display them
upright. This module applies that transform to pixel data so downstream
stages always see an upright image and can discard the EXIF tag.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

# EXIF orientation tag id, per the EXIF spec.
_ORIENTATION_TAG = 0x0112


def read_exif_orientation(path: str | Path) -> int:
    """Return the raw EXIF orientation value (1-8), or 1 (identity) if absent/unreadable."""
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            value = exif.get(_ORIENTATION_TAG, 1)
            return int(value) if value in range(1, 9) else 1
    except Exception:  # noqa: BLE001 - malformed EXIF must not crash the pipeline
        return 1


def normalize_orientation_from_path(path: str | Path) -> np.ndarray:
    """Load an image and return pixel data rotated/flipped upright per its EXIF tag."""
    with Image.open(path) as img:
        upright = ImageOps.exif_transpose(img)
        return np.asarray(upright.convert("RGB"))


def apply_orientation(image: np.ndarray, orientation: int) -> np.ndarray:
    """Apply a raw EXIF orientation value (1-8) to an already-decoded array.

    Useful when the array was decoded separately from the file (e.g. via
    :mod:`receiptlingua.pipeline.preprocess.loading`) and only the
    orientation tag is available, rather than the original file handle.
    """
    if orientation == 1:
        return image
    if orientation == 2:
        return np.fliplr(image)
    if orientation == 3:
        return np.rot90(image, 2)
    if orientation == 4:
        return np.flipud(image)
    if orientation == 5:
        return np.rot90(np.fliplr(image), 1)
    if orientation == 6:
        return np.rot90(image, -1)
    if orientation == 7:
        return np.rot90(np.fliplr(image), -1)
    if orientation == 8:
        return np.rot90(image, 1)
    return image

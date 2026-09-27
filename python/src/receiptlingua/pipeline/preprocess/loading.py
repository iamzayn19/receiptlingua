"""Safe image loading and validation.

Loads image files defensively: rejects malformed files, enforces size
limits, and guards against decompression-bomb style attacks (a small
file that declares an enormous pixel count). Never raises on bad input
-- callers get a structured :class:`LoadResult` with an ``error`` field
instead of a crash, since untrusted images are the normal input to this
pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

# Formats we explicitly support decoding. Anything else is rejected even
# if Pillow could technically open it, to keep the supported surface
# area (and its security exposure) deliberate.
SUPPORTED_FORMATS = frozenset({"JPEG", "PNG", "BMP", "TIFF", "WEBP"})

# Guard against decompression bombs: reject images whose declared pixel
# count exceeds this, before any decoding work happens.
MAX_PIXELS = 64_000_000  # ~64 MP, e.g. a 8000x8000 image

# Guard against absurd aspect ratios (e.g. a 1x60000 image) that can
# still slip under the pixel-count cap.
MAX_DIMENSION = 20_000

MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MB


class ImageLoadError(str):
    """Marker type alias for stable, machine-checkable error codes."""


ERR_EMPTY_FILE = "empty_file"
ERR_FILE_TOO_LARGE = "file_too_large"
ERR_UNREADABLE = "unreadable"
ERR_UNSUPPORTED_FORMAT = "unsupported_format"
ERR_DIMENSIONS_TOO_LARGE = "dimensions_too_large"
ERR_DECOMPRESSION_BOMB = "decompression_bomb_suspected"
ERR_DECODE_FAILED = "decode_failed"


@dataclass(frozen=True)
class LoadResult:
    """Outcome of :func:`load_image`.

    Exactly one of ``image``/``error`` is set on success/failure.
    """

    image: np.ndarray | None
    error: str | None
    width: int | None = None
    height: int | None = None
    format: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.image is not None


def _fail(error: str) -> LoadResult:
    return LoadResult(image=None, error=error)


def load_image(path: str | Path, *, max_pixels: int = MAX_PIXELS) -> LoadResult:
    """Load an image file into an RGB ``numpy`` array (H, W, 3), uint8.

    Always returns a :class:`LoadResult`; never raises for malformed,
    truncated, empty, or non-image input -- those are reported via
    ``result.error`` instead.
    """
    path = Path(path)

    try:
        size = path.stat().st_size
    except OSError:
        return _fail(ERR_UNREADABLE)

    if size == 0:
        return _fail(ERR_EMPTY_FILE)
    if size > MAX_FILE_BYTES:
        return _fail(ERR_FILE_TOO_LARGE)

    try:
        with Image.open(path) as img:
            img.verify()
    except Exception:  # noqa: BLE001 - untrusted input must never crash us
        return _fail(ERR_DECODE_FAILED)

    # Re-open after verify() (which leaves the file in a state that
    # cannot be decoded further) to inspect declared format/dimensions
    # before doing the actual full decode. Pillow's own decompression-bomb
    # guard (Image.DecompressionBombError/Warning) can also fire here for
    # extreme declared dimensions, so this is wrapped broadly too.
    try:
        with Image.open(path) as img:
            fmt = img.format
            width, height = img.size

            if fmt not in SUPPORTED_FORMATS:
                return _fail(ERR_UNSUPPORTED_FORMAT)

            if width <= 0 or height <= 0:
                return _fail(ERR_DECODE_FAILED)

            if width > MAX_DIMENSION or height > MAX_DIMENSION:
                return _fail(ERR_DIMENSIONS_TOO_LARGE)

            declared_pixels = width * height
            if declared_pixels > max_pixels:
                return _fail(ERR_DECOMPRESSION_BOMB)

            img = img.convert("RGB")
            array = np.asarray(img)
    except Exception:  # noqa: BLE001 - includes Pillow's DecompressionBombError
        return _fail(ERR_DECODE_FAILED)

    return LoadResult(image=array, error=None, width=width, height=height, format=fmt)

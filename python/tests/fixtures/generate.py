"""Generate tiny synthetic test fixtures used by the preprocessing tests.

All fixtures are generated programmatically (no downloaded/scraped photos).
Run directly to regenerate the committed PNGs in this directory:

    python python/tests/fixtures/generate.py

Fixtures model a plain white "receipt" with black text-like bars, at a
few KB each so they are cheap to commit to git.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

import numpy as np
from PIL import Image

FIXTURES_DIR = Path(__file__).parent


def _receipt_array(width: int = 200, height: int = 300) -> np.ndarray:
    """A plain white background with black horizontal bars (fake text lines)."""
    img = np.full((height, width), 255, dtype=np.uint8)
    rng = np.random.default_rng(seed=42)
    y = 20
    while y < height - 20:
        bar_width = int(rng.integers(60, width - 30))
        x0 = int(rng.integers(10, max(11, width - bar_width - 10)))
        img[y : y + 6, x0 : x0 + bar_width] = 0
        y += int(rng.integers(14, 22))
    return img


def make_clean_receipt() -> Image.Image:
    return Image.fromarray(_receipt_array(), mode="L").convert("RGB")


def make_rotated_receipt(angle: float = 7.0) -> Image.Image:
    base = make_clean_receipt()
    return base.rotate(angle, expand=True, fillcolor=(255, 255, 255))


def make_low_contrast_receipt() -> Image.Image:
    arr = _receipt_array().astype(np.float32)
    # Compress dynamic range into a narrow mid-gray band.
    arr = 128 + (arr - 128) * 0.12
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, mode="L").convert("RGB")


def make_dark_receipt() -> Image.Image:
    arr = _receipt_array().astype(np.float32) * 0.25
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, mode="L").convert("RGB")


def make_noisy_receipt() -> Image.Image:
    rng = np.random.default_rng(seed=7)
    arr = _receipt_array(width=100, height=140).astype(np.float32)
    noise = rng.normal(0, 30, arr.shape)
    arr = np.clip(arr + noise, 0, 255)
    # Quantize to keep the PNG small (entropy from full float noise
    # otherwise compresses poorly and produces an oversized fixture).
    arr = (np.round(arr / 8) * 8).astype(np.uint8)
    return Image.fromarray(arr, mode="L").convert("RGB")


def make_perspective_receipt() -> Image.Image:
    """A crude quadrilateral warp to emulate a photographed receipt."""
    base = make_clean_receipt()
    w, h = base.size
    coeffs = _perspective_coeffs(
        src=[(0, 0), (w, 0), (w, h), (0, h)],
        dst=[(15, 5), (w - 5, 20), (w - 20, h - 5), (5, h - 15)],
    )
    return base.transform((w, h), Image.Transform.PERSPECTIVE, coeffs, fillcolor=(255, 255, 255))


def _perspective_coeffs(src, dst):
    matrix = []
    for s, d in zip(dst, src, strict=True):
        matrix.append([s[0], s[1], 1, 0, 0, 0, -d[0] * s[0], -d[0] * s[1]])
        matrix.append([0, 0, 0, s[0], s[1], 1, -d[1] * s[0], -d[1] * s[1]])
    A = np.array(matrix, dtype=np.float64)
    B = np.array(dst, dtype=np.float64).reshape(8)
    res = np.linalg.lstsq(A, B, rcond=None)[0]
    return res.tolist()


def write_truncated_fixture(path: Path, source: Path, keep_bytes: int) -> None:
    data = source.read_bytes()
    path.write_bytes(data[:keep_bytes])


def write_zero_byte_fixture(path: Path) -> None:
    path.write_bytes(b"")


def write_fake_image_fixture(path: Path) -> None:
    """A .png file that is actually plain text (wrong-content edge case)."""
    path.write_bytes(b"this is not actually image data, just text with a .png name\n")


def write_decompression_bomb_header(path: Path) -> None:
    """A minimal, syntactically-valid PNG declaring an enormous width/height.

    The IDAT chunk is empty/invalid, so decoding must fail cleanly rather
    than allocate huge buffers. Used to test decompression-bomb guards.
    """
    width = height = 60000  # declared size only; no real pixel data follows

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", b"") + chunk(b"IEND", b"")
    path.write_bytes(png)


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    make_clean_receipt().save(FIXTURES_DIR / "receipt_clean.png")
    make_rotated_receipt().save(FIXTURES_DIR / "receipt_rotated.png")
    make_low_contrast_receipt().save(FIXTURES_DIR / "receipt_low_contrast.png")
    make_dark_receipt().save(FIXTURES_DIR / "receipt_dark.png")
    make_noisy_receipt().save(FIXTURES_DIR / "receipt_noisy.png")
    make_perspective_receipt().save(FIXTURES_DIR / "receipt_perspective.png")

    write_truncated_fixture(
        FIXTURES_DIR / "corrupt_truncated.png",
        FIXTURES_DIR / "receipt_clean.png",
        keep_bytes=200,
    )
    write_zero_byte_fixture(FIXTURES_DIR / "corrupt_zero_byte.png")
    write_fake_image_fixture(FIXTURES_DIR / "corrupt_not_an_image.png")
    write_decompression_bomb_header(FIXTURES_DIR / "corrupt_decompression_bomb.png")

    print(f"Wrote fixtures to {FIXTURES_DIR}")


if __name__ == "__main__":
    main()

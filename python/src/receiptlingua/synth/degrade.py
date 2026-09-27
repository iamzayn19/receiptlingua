"""Deterministic, seeded image degradations for benchmarking.

Every function here takes a PIL ``Image.Image`` and returns a new
``Image.Image``; any randomness is drawn from a ``random.Random``/
``numpy.random.Generator`` seeded from the caller's ``seed`` argument, so
the same ``(image, seed, params)`` always produces the same output
byte-for-byte.

Honesty note (see docs/COMMIT_PLAN.md 171-185): this module implements a
*real subset* of the originally requested degradation wishlist. What is
here actually runs a real transform, verified by
``python/tests/test_synth_degrade.py``. Three items from the original
wishlist were judged too involved to implement for real in this pass and
are **not** in ``DEGRADATIONS`` below -- they are listed in
``DEFERRED_DEGRADATIONS`` purely as documentation of what was NOT done:

- ``thermal_streak`` -- a *lightweight approximation* IS implemented
  (see ``thermal_streak``) using faint horizontal fade bands, not a
  physically-modeled thermal-printer streak.
- ``tear_missing_section`` -- deferred. A convincing torn-paper edge
  (irregular alpha mask, not just a rectangular crop) was not built.
- ``curved_page_dewarp`` -- deferred. ``perspective_warp`` (planar) and
  ``wrinkle_warp`` (local displacement) are implemented, but a genuine
  cylindrical/curved-page warp worth dewarping was not built.
"""

from __future__ import annotations

import io

import cv2
import numpy as np
from PIL import Image


def _to_array(img: Image.Image) -> np.ndarray:
    return np.array(img.convert("RGB"))


def _to_image(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="RGB")


def rotation(img: Image.Image, seed: int, *, max_angle: float = 8.0) -> Image.Image:
    rng = np.random.default_rng(seed)
    angle = float(rng.uniform(-max_angle, max_angle))
    return img.rotate(angle, expand=True, fillcolor=(255, 255, 255), resample=Image.BICUBIC)


def gaussian_blur(img: Image.Image, seed: int, *, max_radius: float = 2.5) -> Image.Image:
    rng = np.random.default_rng(seed)
    radius = float(rng.uniform(1.0, max_radius))
    ksize = max(3, int(radius) * 2 + 1)
    arr = _to_array(img)
    return _to_image(cv2.GaussianBlur(arr, (ksize, ksize), radius))


def motion_blur(img: Image.Image, seed: int, *, max_kernel: int = 9) -> Image.Image:
    rng = np.random.default_rng(seed)
    ksize = int(rng.integers(5, max_kernel + 1))
    if ksize % 2 == 0:
        ksize += 1
    kernel = np.zeros((ksize, ksize), dtype=np.float32)
    angle = float(rng.uniform(0, 180))
    kernel[ksize // 2, :] = 1.0
    center = (ksize / 2, ksize / 2)
    rot = cv2.getRotationMatrix2D(center, angle, 1.0)
    kernel = cv2.warpAffine(kernel, rot, (ksize, ksize))
    kernel = kernel / max(kernel.sum(), 1e-6)
    arr = _to_array(img)
    return _to_image(cv2.filter2D(arr, -1, kernel))


def gaussian_noise(img: Image.Image, seed: int, *, sigma: float = 18.0) -> Image.Image:
    rng = np.random.default_rng(seed)
    arr = _to_array(img).astype(np.float32)
    noise = rng.normal(0, sigma, arr.shape)
    return _to_image(arr + noise)


def salt_pepper_noise(img: Image.Image, seed: int, *, amount: float = 0.02) -> Image.Image:
    rng = np.random.default_rng(seed)
    arr = _to_array(img)
    mask = rng.random(arr.shape[:2])
    arr = arr.copy()
    arr[mask < amount / 2] = 0
    arr[mask > 1 - amount / 2] = 255
    return _to_image(arr)


def jpeg_compression(img: Image.Image, seed: int, *, quality: int = 25) -> Image.Image:
    # Deterministic given `quality` (no randomness needed), seed accepted
    # for interface uniformity with the other degradations.
    del seed
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def brightness_contrast(img: Image.Image, seed: int) -> Image.Image:
    rng = np.random.default_rng(seed)
    brightness = float(rng.uniform(-60, 40))
    contrast = float(rng.uniform(0.5, 1.3))
    arr = _to_array(img).astype(np.float32)
    arr = (arr - 128) * contrast + 128 + brightness
    return _to_image(arr)


def shadow(img: Image.Image, seed: int) -> Image.Image:
    """A soft dark gradient band across part of the image, simulating a
    hand/phone shadow falling across a photographed receipt."""
    rng = np.random.default_rng(seed)
    arr = _to_array(img).astype(np.float32)
    h, w = arr.shape[:2]
    band_start = int(rng.uniform(0, w * 0.6))
    band_width = int(rng.uniform(w * 0.2, w * 0.5))
    x = np.arange(w)
    falloff = np.clip(1 - np.abs(x - (band_start + band_width / 2)) / (band_width / 2 + 1e-6), 0, 1)
    darkness = 0.55  # fraction of brightness removed at the shadow's darkest point
    factor = 1 - falloff * darkness
    arr *= factor[None, :, None]
    return _to_image(arr)


def perspective_warp(img: Image.Image, seed: int, *, max_shift_frac: float = 0.08) -> Image.Image:
    rng = np.random.default_rng(seed)
    w, h = img.size
    max_shift = max_shift_frac * min(w, h)

    def jitter() -> tuple[float, float]:
        dx = float(rng.uniform(-max_shift, max_shift))
        dy = float(rng.uniform(-max_shift, max_shift))
        return (dx, dy)

    src = [(0, 0), (w, 0), (w, h), (0, h)]
    dst = [(x + dx, y + dy) for (x, y), (dx, dy) in zip(src, [jitter() for _ in src], strict=True)]
    coeffs = _perspective_coeffs(src, dst)
    return img.transform((w, h), Image.Transform.PERSPECTIVE, coeffs, fillcolor=(255, 255, 255))


def _perspective_coeffs(src, dst):
    matrix = []
    for s, d in zip(dst, src, strict=True):
        matrix.append([s[0], s[1], 1, 0, 0, 0, -d[0] * s[0], -d[0] * s[1]])
        matrix.append([0, 0, 0, s[0], s[1], 1, -d[1] * s[0], -d[1] * s[1]])
    a = np.array(matrix, dtype=np.float64)
    b = np.array(dst, dtype=np.float64).reshape(8)
    res = np.linalg.lstsq(a, b, rcond=None)[0]
    return res.tolist()


def crop(img: Image.Image, seed: int, *, max_frac: float = 0.12) -> Image.Image:
    """A partial crop -- simulates a photo that cut off part of the receipt."""
    rng = np.random.default_rng(seed)
    w, h = img.size
    left = int(rng.uniform(0, max_frac) * w)
    top = int(rng.uniform(0, max_frac) * h)
    right = w - int(rng.uniform(0, max_frac) * w)
    bottom = h - int(rng.uniform(0, max_frac) * h)
    right = max(right, left + 1)
    bottom = max(bottom, top + 1)
    return img.crop((left, top, right, bottom))


def low_contrast_fade(img: Image.Image, seed: int) -> Image.Image:
    """Simulates faded thermal-paper print: dynamic range compressed
    towards mid-gray."""
    rng = np.random.default_rng(seed)
    fade = float(rng.uniform(0.15, 0.4))
    arr = _to_array(img).astype(np.float32)
    arr = 128 + (arr - 128) * fade
    return _to_image(arr)


def wrinkle_warp(
    img: Image.Image, seed: int, *, amplitude: float = 4.0, wavelength: float = 40.0
) -> Image.Image:
    """A local sinusoidal displacement-map warp approximating creases/
    wrinkles in a photographed paper receipt (best-effort, not a physically
    accurate cloth/paper simulation)."""
    rng = np.random.default_rng(seed)
    arr = _to_array(img)
    h, w = arr.shape[:2]
    phase_x = float(rng.uniform(0, 2 * np.pi))
    phase_y = float(rng.uniform(0, 2 * np.pi))
    yy, xx = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
    dx = amplitude * np.sin(2 * np.pi * yy / wavelength + phase_x)
    dy = amplitude * np.sin(2 * np.pi * xx / wavelength + phase_y)
    map_x = (xx + dx).astype(np.float32)
    map_y = (yy + dy).astype(np.float32)
    warped = cv2.remap(
        arr, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderValue=(255, 255, 255)
    )
    return _to_image(warped)


def thermal_streak(img: Image.Image, seed: int, *, num_streaks: int = 3) -> Image.Image:
    """Lightweight approximation of thermal-printer dropout streaks: a few
    faint/washed-out horizontal bands. NOT a physically modeled
    thermal-head simulation -- documented as best-effort."""
    rng = np.random.default_rng(seed)
    arr = _to_array(img).astype(np.float32)
    h, w = arr.shape[:2]
    for _ in range(num_streaks):
        y0 = int(rng.uniform(0, h))
        band_h = int(rng.uniform(2, max(3, h * 0.03)))
        y1 = min(h, y0 + band_h)
        fade = float(rng.uniform(0.3, 0.8))
        arr[y0:y1, :, :] = 255 - (255 - arr[y0:y1, :, :]) * fade
    return _to_image(arr)


def identity(img: Image.Image, seed: int) -> Image.Image:
    """The "clean" baseline -- no degradation applied."""
    del seed
    return img.copy()


#: name -> callable(img, seed) -> img. This is the set of degradations
#: actually implemented for real; "clean" (identity) is always included as
#: the undegraded baseline case.
DEGRADATIONS: dict[str, object] = {
    "clean": identity,
    "rotation": rotation,
    "gaussian_blur": gaussian_blur,
    "motion_blur": motion_blur,
    "gaussian_noise": gaussian_noise,
    "salt_pepper_noise": salt_pepper_noise,
    "jpeg_compression": jpeg_compression,
    "brightness_contrast": brightness_contrast,
    "shadow": shadow,
    "perspective_warp": perspective_warp,
    "crop": crop,
    "low_contrast_fade": low_contrast_fade,
    "wrinkle_warp": wrinkle_warp,
    "thermal_streak": thermal_streak,
}

#: Documented but NOT implemented in this pass -- see module docstring.
#: Present only so tooling/docs can enumerate "known gaps" without a human
#: having to cross-reference prose.
DEFERRED_DEGRADATIONS: tuple[str, ...] = (
    "tear_missing_section",
    "curved_page_dewarp",
)

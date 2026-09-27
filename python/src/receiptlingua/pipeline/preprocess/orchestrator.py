"""Preprocessing candidate pipeline orchestrator.

Chains a configurable subset of the preprocessing stages based on the
image-quality heuristic score (see ``quality.py``), rather than always
running every technique on every image. A clean, well-lit, sharp
receipt photo only needs the cheap always-on stages (load, EXIF
normalize, deskew, grayscale); a blurry/dark/low-contrast one
escalates to CLAHE, gamma correction, stronger denoising, and
sharpening.

This module produces "preprocessing candidates": one or more processed
variants of the input image that the OCR engine layer (milestone 56-80)
can try, in order, stopping early on a confident result. For v0 this
orchestrator returns a single best-effort candidate per quality tier;
returning multiple candidates for the engine layer to race is left as
a follow-up once OCR confidence signals exist to compare against.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np

from receiptlingua.pipeline.preprocess import (
    clahe as clahe_mod,
)
from receiptlingua.pipeline.preprocess import (
    denoise,
    gamma,
    perspective,
    sharpen,
)
from receiptlingua.pipeline.preprocess.deskew import deskew
from receiptlingua.pipeline.preprocess.exif_orientation import apply_orientation
from receiptlingua.pipeline.preprocess.grayscale import to_grayscale
from receiptlingua.pipeline.preprocess.loading import LoadResult, load_image
from receiptlingua.pipeline.preprocess.quality import QualityScore, score_quality


class Mode(str, Enum):
    FAST = "fast"
    ACCURATE = "accurate"
    AUTO = "auto"


@dataclass(frozen=True)
class PreprocessResult:
    image: np.ndarray  # final single-channel uint8 candidate
    mode_used: Mode
    quality: QualityScore
    steps_applied: tuple[str, ...]
    load_error: str | None = None

    @property
    def ok(self) -> bool:
        return self.load_error is None


def _resolve_mode(mode: Mode, quality: QualityScore) -> Mode:
    if mode != Mode.AUTO:
        return mode
    return Mode.ACCURATE if quality.needs_accurate_mode else Mode.FAST


def preprocess_array(
    image: np.ndarray,
    *,
    mode: Mode = Mode.AUTO,
    exif_orientation: int = 1,
    correct_document_boundary: bool = True,
) -> PreprocessResult:
    """Run the preprocessing candidate pipeline on an already-decoded image array."""
    steps: list[str] = []

    working = apply_orientation(image, exif_orientation)
    if exif_orientation != 1:
        steps.append("exif_orientation")

    if correct_document_boundary:
        boundary_before = working
        working = perspective.detect_and_correct(working)
        if working is not boundary_before:
            steps.append("perspective_correction")

    deskew_result = deskew(working)
    working = deskew_result.image
    if abs(deskew_result.angle_degrees) > 0.1:
        steps.append("deskew")

    quality = score_quality(working)
    resolved_mode = _resolve_mode(mode, quality)

    gray = to_grayscale(working)
    steps.append("grayscale")

    if resolved_mode == Mode.FAST:
        gray = denoise.denoise_fast(gray)
        steps.append("denoise_fast")
    else:
        if quality.is_poorly_lit:
            gray = gamma.auto_gamma_correct(gray)
            steps.append("auto_gamma")
        if quality.is_low_contrast:
            gray = clahe_mod.apply_clahe(gray)
            steps.append("clahe")
        if quality.is_blurry:
            gray = denoise.denoise_accurate(gray)
            steps.append("denoise_accurate")
            gray = sharpen.unsharp_mask(gray, amount=1.5)
            steps.append("sharpen")
        else:
            gray = denoise.denoise_fast(gray)
            steps.append("denoise_fast")

    return PreprocessResult(
        image=gray,
        mode_used=resolved_mode,
        quality=quality,
        steps_applied=tuple(steps),
    )


def preprocess_file(
    path: str,
    *,
    mode: Mode = Mode.AUTO,
    correct_document_boundary: bool = True,
) -> PreprocessResult:
    """Load an image file and run the full preprocessing candidate pipeline.

    Returns a :class:`PreprocessResult` with ``load_error`` set (and a
    zero-sized placeholder image) rather than raising if the file
    cannot be loaded -- callers should check ``result.ok`` before using
    ``result.image``.
    """
    load_result: LoadResult = load_image(path)
    if not load_result.ok:
        return PreprocessResult(
            image=np.zeros((0, 0), dtype=np.uint8),
            mode_used=mode,
            quality=score_quality(np.zeros((1, 1), dtype=np.uint8)),
            steps_applied=(),
            load_error=load_result.error,
        )

    from receiptlingua.pipeline.preprocess.exif_orientation import read_exif_orientation

    orientation = read_exif_orientation(path)
    return preprocess_array(
        load_result.image,
        mode=mode,
        exif_orientation=orientation,
        correct_document_boundary=correct_document_boundary,
    )

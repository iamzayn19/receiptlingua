"""Abstract OCR engine interface.

Every backend adapter (Tesseract, PaddleOCR, ...) implements this ABC.
Callers depend only on this interface, never on a concrete backend, so
mode selection and the sidecar protocol layer stay backend-agnostic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from receiptlingua.engines.types import EngineResult


class OCREngine(ABC):
    """Backend-agnostic OCR engine.

    Implementations must raise :class:`receiptlingua.engines.errors.EngineError`
    subclasses (never bare exceptions) for any expected failure mode --
    missing model/language data, an image the backend cannot process, or
    the backend being unavailable at all in this environment.
    """

    #: Stable machine-readable backend name, e.g. "tesseract", "paddleocr".
    #: Must match the ``engine`` field in response.schema.json.
    name: str

    @abstractmethod
    def is_available(self) -> bool:
        """Whether this backend can actually run in the current environment.

        Must not raise and must not touch the network. Checked before
        :meth:`recognize` is ever called so callers can fall back to
        another engine, or surface UNSUPPORTED_BACKEND, without a crash.
        """

    @abstractmethod
    def supported_languages(self) -> tuple[str, ...]:
        """BCP-47-ish language codes this engine can currently recognize.

        Reflects what is actually installed/cached right now (e.g. which
        Tesseract language data files are present), not the backend's
        theoretical maximum support.
        """

    @abstractmethod
    def recognize(
        self,
        image: np.ndarray,
        *,
        languages: tuple[str, ...] = (),
    ) -> EngineResult:
        """Run OCR on a single already-preprocessed image.

        ``image`` is a 2D (grayscale) or 3D (RGB) uint8 numpy array, the
        output of the preprocessing pipeline. Implementations must not
        hallucinate text for illegible/blank regions -- return an empty
        or low-confidence/``illegible``-status line instead of guessing.
        """

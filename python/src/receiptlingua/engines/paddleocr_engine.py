"""PaddleOCR backend adapter.

NOT VALIDATED in this environment: as of this writing, `paddlepaddle` has
no distributable build for Python 3.14 (see
docs/adr/0002-ocr-backend-selection.md for the exact `pip install` failure
output). This class defines the intended integration shape -- once
paddlepaddle/paddleocr are importable (either because upstream ships a
3.14-compatible build, or because this backend is run inside a separate
sidecar venv pinned to Python 3.11/3.12) the recognize() implementation
below is what needs filling in and testing.

Every method degrades to a clear ``UNSUPPORTED_BACKEND`` error rather than
crashing with an ImportError, per the "runtime capability check" design
called out in the architecture doc.
"""

from __future__ import annotations

import importlib.util

import numpy as np

from receiptlingua.engines.base import OCREngine
from receiptlingua.engines.errors import UnsupportedBackendError
from receiptlingua.engines.types import EngineResult

# PaddleOCR's PP-OCRv4/v5 multilingual recognition models cover Latin,
# Arabic, Devanagari-family, Cyrillic, and CJK scripts -- see the ADR for
# why this remains the target primary backend for the "109 languages"
# goal once it can actually be installed here.
_INTENDED_LANGUAGES: tuple[str, ...] = ()


class PaddleOCREngine(OCREngine):
    name = "paddleocr"

    def __init__(self):
        self._ocr = None

    def is_available(self) -> bool:
        return (
            importlib.util.find_spec("paddle") is not None
            and importlib.util.find_spec("paddleocr") is not None
        )

    def supported_languages(self) -> tuple[str, ...]:
        if not self.is_available():
            return ()
        return _INTENDED_LANGUAGES

    def _load(self):
        if not self.is_available():
            raise UnsupportedBackendError(
                self.name,
                "paddlepaddle/paddleocr not importable in this Python environment "
                "-- see docs/adr/0002-ocr-backend-selection.md",
            )
        if self._ocr is None:
            from paddleocr import PaddleOCR  # noqa: PLC0415 -- intentional lazy import

            self._ocr = PaddleOCR(use_angle_cls=True, lang="en")
        return self._ocr

    def recognize(
        self,
        image: np.ndarray,
        *,
        languages: tuple[str, ...] = (),
    ) -> EngineResult:
        # Raises UnsupportedBackendError immediately in this environment --
        # intentionally not implemented further until installability is
        # confirmed, so we never ship an untested code path as if it works.
        self._load()
        raise NotImplementedError(
            "PaddleOCR became importable but recognize() has not been "
            "implemented/tested yet -- fill in once install is verified."
        )

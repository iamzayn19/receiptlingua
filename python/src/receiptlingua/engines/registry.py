"""Engine registry/factory.

Central place to look up a backend by name. Kept deliberately tiny --
just enough indirection that mode selection and the future sidecar
protocol layer don't need to import concrete engine classes directly.
"""

from __future__ import annotations

from receiptlingua.engines.base import OCREngine
from receiptlingua.engines.errors import UnsupportedBackendError
from receiptlingua.engines.paddleocr_engine import PaddleOCREngine
from receiptlingua.engines.tesseract_engine import TesseractEngine

_ENGINE_CLASSES: dict[str, type[OCREngine]] = {
    "tesseract": TesseractEngine,
    "paddleocr": PaddleOCREngine,
}


def available_engine_names() -> tuple[str, ...]:
    return tuple(_ENGINE_CLASSES.keys())


def get_engine(name: str) -> OCREngine:
    """Instantiate a backend by name. Does not check availability -- call
    ``engine.is_available()`` before ``recognize()``."""
    engine_class = _ENGINE_CLASSES.get(name)
    if engine_class is None:
        raise UnsupportedBackendError(
            name, f"no such engine registered (known: {', '.join(available_engine_names())})"
        )
    return engine_class()


def get_default_engine() -> OCREngine:
    """The first available (installed/loadable) engine, preferring Tesseract.

    Preference order matches docs/adr/0002-ocr-backend-selection.md:
    Tesseract is the validated default backend; PaddleOCR is preferred
    once it is actually installable (it is not, on this interpreter).
    """
    for name in ("paddleocr", "tesseract"):
        engine = get_engine(name)
        if engine.is_available():
            return engine
    raise UnsupportedBackendError(
        "none", "no OCR backend is available in this environment (checked: paddleocr, tesseract)"
    )

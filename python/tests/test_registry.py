"""Tests for the engine registry/factory and PaddleOCR's UNSUPPORTED_BACKEND guard."""

from __future__ import annotations

import numpy as np
import pytest

from receiptlingua.engines.errors import UnsupportedBackendError
from receiptlingua.engines.paddleocr_engine import PaddleOCREngine
from receiptlingua.engines.registry import available_engine_names, get_default_engine, get_engine
from receiptlingua.engines.tesseract_engine import TesseractEngine


def test_available_engine_names_lists_known_backends():
    assert set(available_engine_names()) == {"tesseract", "paddleocr"}


def test_get_engine_returns_correct_class():
    assert isinstance(get_engine("tesseract"), TesseractEngine)
    assert isinstance(get_engine("paddleocr"), PaddleOCREngine)


def test_get_engine_unknown_name_raises_unsupported_backend():
    with pytest.raises(UnsupportedBackendError):
        get_engine("not-a-real-backend")


def test_get_default_engine_returns_an_available_engine():
    engine = get_default_engine()
    assert engine.is_available()


def test_paddleocr_engine_not_available_on_this_interpreter_raises_clear_error():
    """Documents the current environment's real constraint (see ADR 0002):
    paddlepaddle/paddleocr are not importable on Python 3.14 here, so the
    adapter must fail with UNSUPPORTED_BACKEND rather than an ImportError.
    """
    engine = PaddleOCREngine()
    if engine.is_available():
        pytest.skip("paddleocr is importable in this environment; guard not exercised")
    with pytest.raises(UnsupportedBackendError) as exc_info:
        engine.recognize(np.zeros((10, 10), dtype=np.uint8))
    assert exc_info.value.code == "UNSUPPORTED_BACKEND"

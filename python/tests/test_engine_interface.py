"""Conformance tests for the OCREngine abstract interface using a fake engine.

No real OCR backend is exercised here -- this only checks that anything
implementing OCREngine produces EngineResult objects with the shape the
protocol response schema expects.
"""

from __future__ import annotations

import numpy as np
import pytest

from receiptlingua.engines.base import OCREngine
from receiptlingua.engines.errors import EngineError, UnsupportedBackendError
from receiptlingua.engines.types import BBox, EngineResult, EngineTextLine


class FakeEngine(OCREngine):
    name = "fake"

    def __init__(self, *, available: bool = True, languages: tuple[str, ...] = ("en",)):
        self._available = available
        self._languages = languages

    def is_available(self) -> bool:
        return self._available

    def supported_languages(self) -> tuple[str, ...]:
        return self._languages

    def recognize(self, image: np.ndarray, *, languages: tuple[str, ...] = ()) -> EngineResult:
        if not self._available:
            raise UnsupportedBackendError(self.name, "fake engine marked unavailable")
        line = EngineTextLine(
            text="FAKE TEXT",
            bbox=BBox(0, 0, image.shape[1], image.shape[0]),
            confidence=0.9,
            status="ok",
        )
        return EngineResult(engine=self.name, engine_version="0.0-fake", text_lines=(line,))


def test_fake_engine_satisfies_interface():
    engine = FakeEngine()
    assert isinstance(engine, OCREngine)
    assert engine.is_available()
    assert "en" in engine.supported_languages()


def test_recognize_returns_engine_result_with_expected_shape():
    engine = FakeEngine()
    image = np.zeros((50, 100), dtype=np.uint8)
    result = engine.recognize(image)

    assert isinstance(result, EngineResult)
    assert result.engine == "fake"
    assert result.text_lines[0].status in (
        "ok",
        "illegible",
        "truncated",
        "missing_region",
        "uncertain",
    )
    assert 0.0 <= result.text_lines[0].confidence <= 1.0
    assert result.full_text == "FAKE TEXT"
    assert not result.is_empty


def test_unavailable_engine_raises_engine_error_not_bare_exception():
    engine = FakeEngine(available=False)
    with pytest.raises(EngineError) as exc_info:
        engine.recognize(np.zeros((10, 10), dtype=np.uint8))
    assert exc_info.value.code == "UNSUPPORTED_BACKEND"
    # Must be serializable into a protocol-conformant error envelope.
    payload = exc_info.value.to_dict()
    assert payload["code"] == "UNSUPPORTED_BACKEND"
    assert "message" in payload


def test_empty_result_is_empty_and_has_no_lines():
    result = EngineResult(engine="fake", engine_version="0.0")
    assert result.is_empty
    assert result.full_text == ""


def test_cannot_instantiate_abstract_engine_directly():
    with pytest.raises(TypeError):
        OCREngine()  # abstract methods unimplemented

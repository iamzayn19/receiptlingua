"""Real end-to-end smoke tests against the PaddleOCR sidecar backend.

PaddleOCR cannot run in-process on this package's own Python (3.14 has no
`paddlepaddle` build -- see docs/adr/0002-ocr-backend-selection.md), so
these tests exercise the real subprocess sidecar: they only run for real
when RECEIPTLINGUA_PADDLE_PYTHON is set to a Python 3.11-3.13 interpreter
with `paddlepaddle`/`paddleocr` installed (see the ADR for how to set one
up). Otherwise they skip cleanly, mirroring how the Tamil/Arabic
Tesseract language-pack tests skip when their trained data isn't
installed -- this is a local, offline setup step, never something the
pipeline attempts automatically at runtime or over the network.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from receiptlingua.engines.paddleocr_engine import PaddleOCREngine

FIXTURES_DIR = Path(__file__).parent / "fixtures"

engine = PaddleOCREngine()
pytestmark = pytest.mark.skipif(
    not engine.is_available(),
    reason="RECEIPTLINGUA_PADDLE_PYTHON not set to a usable sidecar interpreter",
)


def _load(name: str) -> np.ndarray:
    return np.array(Image.open(FIXTURES_DIR / name))


def test_english_text_fixture_produces_nonempty_recognizable_lines():
    image = _load("receipt_text_eng.png")
    result = engine.recognize(image, languages=("en",))

    assert not result.is_empty
    assert result.engine == "paddleocr"
    assert result.engine_version

    full_text_upper = result.full_text.upper()
    assert "CORNER" in full_text_upper or "STORE" in full_text_upper
    assert "6.48" in result.full_text or "6.4" in result.full_text

    for line in result.text_lines:
        assert 0.0 <= line.confidence <= 1.0
        assert line.status in ("ok", "illegible", "truncated", "missing_region", "uncertain")


def test_tamil_text_fixture_produces_nonempty_lines():
    image = _load("receipt_text_tam.png")
    result = engine.recognize(image, languages=("ta",))
    assert not result.is_empty
    assert len(result.full_text.strip()) > 0


def test_arabic_text_fixture_produces_nonempty_lines():
    image = _load("receipt_text_ara.png")
    result = engine.recognize(image, languages=("ar",))
    assert not result.is_empty
    assert len(result.full_text.strip()) > 0


def test_blank_image_does_not_hallucinate_text():
    blank = np.full((100, 300), 255, dtype=np.uint8)
    result = engine.recognize(blank, languages=("en",))
    assert result.full_text.strip() == "" or all(
        line.status != "ok" for line in result.text_lines
    )


def test_unavailable_backend_raises_unsupported_backend_error(monkeypatch):
    from receiptlingua.engines.errors import UnsupportedBackendError

    unset_engine = PaddleOCREngine(sidecar_python="/nonexistent/python")
    assert not unset_engine.is_available()
    with pytest.raises(UnsupportedBackendError):
        unset_engine.recognize(_load("receipt_text_eng.png"))

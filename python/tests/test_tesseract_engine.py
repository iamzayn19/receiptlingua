"""Real end-to-end smoke tests against the Tesseract backend.

Uses the real-text fixtures generated in tests/fixtures/generate.py
(genuine rendered glyphs via PIL ImageDraw + system fonts, not the
black-bar placeholders used by the preprocessing tests). English is
expected to work in any environment with the `tesseract` binary and its
bundled `eng` language data. Tamil/Arabic additionally require
`tam.traineddata`/`ara.traineddata` to be discoverable (either via the
system Tesseract's own tessdata directory, or via
RECEIPTLINGUA_CACHE_DIR's tessdata/ subdirectory) -- see
docs/adr/0002-ocr-backend-selection.md for how to obtain them. Those
tests skip cleanly, rather than failing, when the language data isn't
present, since fetching it is a one-time offline setup step, not
something the pipeline should ever attempt automatically at runtime.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from receiptlingua.engines.tesseract_engine import TesseractEngine

FIXTURES_DIR = Path(__file__).parent / "fixtures"

engine = TesseractEngine()
pytestmark = pytest.mark.skipif(
    not engine.is_available(), reason="tesseract binary or pytesseract not available"
)


def _load(name: str) -> np.ndarray:
    return np.array(Image.open(FIXTURES_DIR / name))


def test_english_text_fixture_produces_nonempty_recognizable_lines():
    image = _load("receipt_text_eng.png")
    result = engine.recognize(image)

    assert not result.is_empty
    assert result.engine == "tesseract"
    assert result.engine_version

    # Don't over-assert exact OCR output, but the merchant name and total
    # should show up somewhere in a genuinely-recognized result.
    full_text_upper = result.full_text.upper()
    assert "CORNER" in full_text_upper or "STORE" in full_text_upper
    assert "6.48" in result.full_text or "6.4" in result.full_text

    for line in result.text_lines:
        assert line.bbox.width > 0
        assert line.bbox.height > 0
        assert 0.0 <= line.confidence <= 1.0
        assert line.status in ("ok", "illegible", "truncated", "missing_region", "uncertain")


def _tam_available() -> bool:
    return "tam" in engine.supported_languages()


def _ara_available() -> bool:
    return "ara" in engine.supported_languages()


@pytest.mark.skipif(not _tam_available(), reason="tam.traineddata not installed/cached")
def test_tamil_text_fixture_produces_nonempty_lines():
    image = _load("receipt_text_tam.png")
    result = engine.recognize(image, languages=("tam",))
    assert not result.is_empty
    assert len(result.full_text.strip()) > 0


@pytest.mark.skipif(not _ara_available(), reason="ara.traineddata not installed/cached")
def test_arabic_text_fixture_produces_nonempty_lines():
    image = _load("receipt_text_ara.png")
    result = engine.recognize(image, languages=("ara",))
    assert not result.is_empty
    assert len(result.full_text.strip()) > 0


def test_blank_image_does_not_hallucinate_text():
    blank = np.full((100, 300), 255, dtype=np.uint8)
    result = engine.recognize(blank)
    # Must not invent text for a blank region -- either no lines, or
    # lines are empty/low-confidence, never confident fabricated content.
    assert result.full_text.strip() == "" or all(
        line.status != "ok" for line in result.text_lines
    )

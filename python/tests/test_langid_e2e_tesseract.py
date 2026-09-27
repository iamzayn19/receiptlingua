"""Real end-to-end test: run TesseractEngine on the genuine rendered-text
fixtures from the OCR engine milestone, then run language/script tagging
on its actual recognized output. Doesn't assert perfect OCR correctness
(the engine is already imperfect on Tamil/Arabic per ADR 0002) -- asserts
that script detection on whatever text Tesseract actually produced is
sane: Tamil script shows up on the Tamil fixture, Arabic on the Arabic
fixture, Latin on the English fixture.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from receiptlingua.engines.tesseract_engine import TesseractEngine
from receiptlingua.langid.tagging import tag_document

FIXTURES_DIR = Path(__file__).parent / "fixtures"

engine = TesseractEngine()
pytestmark = pytest.mark.skipif(
    not engine.is_available(), reason="tesseract binary or pytesseract not available"
)


def _load(name: str) -> np.ndarray:
    return np.array(Image.open(FIXTURES_DIR / name))


def test_english_fixture_tags_latin_script_and_english_language():
    image = _load("receipt_text_eng.png")
    result = engine.recognize(image)
    assert not result.is_empty

    lines = [line.text for line in result.text_lines if line.text.strip()]
    doc = tag_document(lines)

    assert "Latn" in doc.scripts
    codes = [entry["code"] for entry in doc.languages]
    # English should be present if any language was confident enough to
    # register at all; a receipt this short/numeric may also yield no
    # confident language, which is an acceptable, honest outcome.
    assert codes == [] or "en" in codes


def _tam_available() -> bool:
    return "tam" in engine.supported_languages()


def _ara_available() -> bool:
    return "ara" in engine.supported_languages()


@pytest.mark.skipif(not _tam_available(), reason="tam.traineddata not installed/cached")
def test_tamil_fixture_tags_tamil_script():
    image = _load("receipt_text_tam.png")
    result = engine.recognize(image, languages=("tam",))
    assert not result.is_empty

    lines = [line.text for line in result.text_lines if line.text.strip()]
    doc = tag_document(lines)
    assert "Taml" in doc.scripts


@pytest.mark.skipif(not _ara_available(), reason="ara.traineddata not installed/cached")
def test_arabic_fixture_tags_arabic_script():
    image = _load("receipt_text_ara.png")
    result = engine.recognize(image, languages=("ara",))
    assert not result.is_empty

    lines = [line.text for line in result.text_lines if line.text.strip()]
    doc = tag_document(lines)
    assert "Arab" in doc.scripts

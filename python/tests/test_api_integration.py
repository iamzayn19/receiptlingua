"""Real end-to-end integration tests for the public ``ReceiptOCR`` API.

Runs the actual full pipeline (preprocess -> OCR -> language/script
tagging -> structured field extraction) against the same real-text
fixtures used by the engine-layer smoke tests
(``tests/test_tesseract_engine.py``). English is expected to work in any
environment with the ``tesseract`` binary and its bundled ``eng``
language data (true in CI and in this checkout). Tamil/Arabic are
included honestly: this pipeline only actually engages non-English
Tesseract language data when the caller explicitly requests it via
``ReceiptOCR(languages=...)`` (documented in ``api.py`` -- there is no
language-ID pre-pass yet), and even then those tests skip cleanly rather
than fail when the corresponding ``.traineddata`` file is not installed,
matching every other language-data-dependent test in this suite.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from receiptlingua import ReceiptOCR, ReceiptOCRError
from receiptlingua.engines.tesseract_engine import TesseractEngine

FIXTURES_DIR = Path(__file__).parent / "fixtures"
_PROTOCOL_SCHEMA_DIR = Path(__file__).parent.parent.parent / "protocol" / "schema"
SCHEMA_PATH = _PROTOCOL_SCHEMA_DIR / "response.schema.json"
ERROR_SCHEMA_PATH = _PROTOCOL_SCHEMA_DIR / "error.schema.json"

_tesseract = TesseractEngine()
pytestmark = pytest.mark.skipif(
    not _tesseract.is_available(), reason="tesseract binary or pytesseract not available"
)


def _response_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def _error_schema() -> dict:
    return json.loads(ERROR_SCHEMA_PATH.read_text())


def _lang_available(lang: str) -> bool:
    return lang in _tesseract.supported_languages()


def test_scan_english_fixture_end_to_end_matches_schema():
    ocr = ReceiptOCR()
    result = ocr.scan(str(FIXTURES_DIR / "receipt_text_eng.png"))

    assert result.engine == "tesseract"
    assert result.schema_version == "0.1.0"
    assert result.mode in ("fast", "accurate", "auto")
    assert result.full_text.strip() != ""
    assert len(result.text_lines) > 0
    assert result.image["width"] > 0 and result.image["height"] > 0

    jsonschema.validate(result.to_dict(), _response_schema())


def test_scan_english_fixture_extracts_total_field():
    ocr = ReceiptOCR()
    result = ocr.scan(str(FIXTURES_DIR / "receipt_text_eng.png"))
    # receipt_text_eng.png is rendered with a literal "TOTAL 6.48" line
    # (see tests/fixtures/generate.py) -- assert the real extracted
    # value, not just that *some* field exists.
    assert result.fields["total"]["status"] == "ok"
    assert result.fields["total"]["value"] == 6.48


def test_scan_tamil_fixture_is_honest_about_language_pack_availability():
    ocr = ReceiptOCR(languages=("tam",))
    path = str(FIXTURES_DIR / "receipt_text_tam.png")
    if _lang_available("tam"):
        result = ocr.scan(path)
        jsonschema.validate(result.to_dict(), _response_schema())
    else:
        with pytest.raises(ReceiptOCRError) as excinfo:
            ocr.scan(path)
        assert excinfo.value.code == "OCR_FAILED"


def test_scan_arabic_fixture_is_honest_about_language_pack_availability():
    ocr = ReceiptOCR(languages=("ara",))
    path = str(FIXTURES_DIR / "receipt_text_ara.png")
    if _lang_available("ara"):
        result = ocr.scan(path)
        jsonschema.validate(result.to_dict(), _response_schema())
    else:
        with pytest.raises(ReceiptOCRError) as excinfo:
            ocr.scan(path)
        assert excinfo.value.code == "OCR_FAILED"


def test_scan_rejects_zero_byte_file_with_invalid_image_error():
    ocr = ReceiptOCR()
    with pytest.raises(ReceiptOCRError) as excinfo:
        ocr.scan(str(FIXTURES_DIR / "corrupt_zero_byte.png"))
    assert excinfo.value.code == "INVALID_IMAGE"
    jsonschema.validate(excinfo.value.to_dict(), _error_schema())


def test_scan_rejects_non_image_file():
    ocr = ReceiptOCR()
    with pytest.raises(ReceiptOCRError) as excinfo:
        ocr.scan(str(FIXTURES_DIR / "corrupt_not_an_image.png"))
    assert excinfo.value.code == "INVALID_IMAGE"


def test_scan_rejects_missing_file():
    ocr = ReceiptOCR()
    with pytest.raises(ReceiptOCRError) as excinfo:
        ocr.scan("this/path/does/not/exist.png")
    assert excinfo.value.code == "INVALID_IMAGE"


def test_scan_accepts_bytes_input():
    ocr = ReceiptOCR()
    data = (FIXTURES_DIR / "receipt_text_eng.png").read_bytes()
    result = ocr.scan(data)
    assert result.full_text.strip() != ""


def test_scan_accepts_pil_image_input():
    from PIL import Image

    ocr = ReceiptOCR()
    img = Image.open(FIXTURES_DIR / "receipt_text_eng.png")
    result = ocr.scan(img)
    assert result.full_text.strip() != ""


def test_invalid_mode_raises_invalid_configuration():
    with pytest.raises(ReceiptOCRError) as excinfo:
        ReceiptOCR(mode="not-a-real-mode")
    assert excinfo.value.code == "INVALID_CONFIGURATION"


def test_invalid_backend_raises_unsupported_backend():
    ocr = ReceiptOCR(backend="not-a-real-backend")
    with pytest.raises(ReceiptOCRError) as excinfo:
        ocr.scan(str(FIXTURES_DIR / "receipt_text_eng.png"))
    assert excinfo.value.code == "UNSUPPORTED_BACKEND"


def test_result_to_json_round_trips():
    ocr = ReceiptOCR()
    result = ocr.scan(str(FIXTURES_DIR / "receipt_text_eng.png"))
    parsed = json.loads(result.to_json())
    assert parsed["full_text"] == result.full_text
    assert parsed["fields"]["total"] == result.fields["total"]

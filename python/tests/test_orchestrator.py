from pathlib import Path

import numpy as np

from receiptlingua.pipeline.preprocess import loading
from receiptlingua.pipeline.preprocess.orchestrator import (
    Mode,
    preprocess_array,
    preprocess_file,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_auto_mode_uses_fast_path_for_clean_receipt():
    result = loading.load_image(FIXTURES / "receipt_clean.png")
    out = preprocess_array(result.image, mode=Mode.AUTO)
    assert out.ok
    assert out.mode_used == Mode.FAST
    assert "denoise_fast" in out.steps_applied
    assert "clahe" not in out.steps_applied


def test_auto_mode_escalates_for_low_contrast_receipt():
    result = loading.load_image(FIXTURES / "receipt_low_contrast.png")
    out = preprocess_array(result.image, mode=Mode.AUTO)
    assert out.mode_used == Mode.ACCURATE
    assert "clahe" in out.steps_applied


def test_auto_mode_escalates_for_dark_receipt():
    result = loading.load_image(FIXTURES / "receipt_dark.png")
    out = preprocess_array(result.image, mode=Mode.AUTO)
    assert out.mode_used == Mode.ACCURATE
    assert "auto_gamma" in out.steps_applied


def test_forced_fast_mode_never_escalates():
    result = loading.load_image(FIXTURES / "receipt_dark.png")
    out = preprocess_array(result.image, mode=Mode.FAST)
    assert out.mode_used == Mode.FAST
    assert "clahe" not in out.steps_applied
    assert "auto_gamma" not in out.steps_applied


def test_forced_accurate_mode_always_used():
    result = loading.load_image(FIXTURES / "receipt_clean.png")
    out = preprocess_array(result.image, mode=Mode.ACCURATE)
    assert out.mode_used == Mode.ACCURATE


def test_output_is_grayscale_uint8():
    result = loading.load_image(FIXTURES / "receipt_clean.png")
    out = preprocess_array(result.image)
    assert out.image.ndim == 2
    assert out.image.dtype == np.uint8


def test_deskew_step_recorded_for_rotated_fixture():
    result = loading.load_image(FIXTURES / "receipt_rotated.png")
    out = preprocess_array(result.image)
    assert "deskew" in out.steps_applied


def test_perspective_correction_applied_when_boundary_found():
    result = loading.load_image(FIXTURES / "receipt_on_background.png")
    out = preprocess_array(result.image, correct_document_boundary=True)
    assert "perspective_correction" in out.steps_applied


def test_perspective_correction_disabled_when_requested():
    result = loading.load_image(FIXTURES / "receipt_on_background.png")
    out = preprocess_array(result.image, correct_document_boundary=False)
    assert "perspective_correction" not in out.steps_applied


def test_preprocess_file_end_to_end():
    out = preprocess_file(str(FIXTURES / "receipt_clean.png"))
    assert out.ok
    assert out.image.size > 0


def test_preprocess_file_reports_load_error_without_raising():
    out = preprocess_file(str(FIXTURES / "corrupt_zero_byte.png"))
    assert not out.ok
    assert out.load_error is not None
    assert out.image.size == 0


def test_preprocess_file_never_raises_on_any_corrupt_fixture():
    for name in [
        "corrupt_truncated.png",
        "corrupt_not_an_image.png",
        "corrupt_decompression_bomb.png",
        "does_not_exist.png",
    ]:
        out = preprocess_file(str(FIXTURES / name))
        assert not out.ok

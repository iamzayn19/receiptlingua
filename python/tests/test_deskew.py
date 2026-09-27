from pathlib import Path

import numpy as np

from receiptlingua.pipeline.preprocess import deskew, loading

FIXTURES = Path(__file__).parent / "fixtures"


def test_estimate_skew_angle_near_zero_for_clean_receipt():
    result = loading.load_image(FIXTURES / "receipt_clean.png")
    angle = deskew.estimate_skew_angle(result.image)
    assert abs(angle) < 2.0


def test_estimate_skew_angle_detects_rotated_receipt():
    result = loading.load_image(FIXTURES / "receipt_rotated.png")
    angle = deskew.estimate_skew_angle(result.image)
    assert abs(angle) > 2.0


def test_deskew_reduces_skew_of_rotated_receipt():
    result = loading.load_image(FIXTURES / "receipt_rotated.png")
    before = abs(deskew.estimate_skew_angle(result.image))

    deskewed = deskew.deskew(result.image)
    after = abs(deskew.estimate_skew_angle(deskewed.image))

    assert after < before
    assert after < 1.5


def test_deskew_is_near_identity_for_already_upright_image():
    result = loading.load_image(FIXTURES / "receipt_clean.png")
    deskewed = deskew.deskew(result.image)
    assert abs(deskewed.angle_degrees) < 2.0


def test_rotate_image_zero_angle_is_identity():
    arr = np.arange(3 * 4 * 3, dtype=np.uint8).reshape(3, 4, 3)
    rotated = deskew.rotate_image(arr, 0.0)
    assert rotated is arr


def test_rotate_image_expands_canvas_for_nonzero_angle():
    arr = np.zeros((100, 50, 3), dtype=np.uint8)
    rotated = deskew.rotate_image(arr, 45.0)
    assert rotated.shape[0] >= arr.shape[0]
    assert rotated.shape[1] >= arr.shape[1]


def test_estimate_skew_angle_handles_blank_image():
    blank = np.full((50, 50), 255, dtype=np.uint8)
    angle = deskew.estimate_skew_angle(blank)
    assert angle == 0.0

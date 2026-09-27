from pathlib import Path

import numpy as np

from receiptlingua.pipeline.preprocess import loading, perspective

FIXTURES = Path(__file__).parent / "fixtures"


def test_detects_boundary_on_high_contrast_background():
    result = loading.load_image(FIXTURES / "receipt_on_background.png")
    boundary = perspective.detect_document_boundary(result.image)
    assert boundary.found
    assert boundary.corners is not None
    assert boundary.corners.shape == (4, 2)


def test_no_boundary_found_on_flat_background():
    # The clean receipt fixture has no background at all (edge-to-edge
    # white), so there is no boundary to find -- this must report
    # found=False rather than guessing at a spurious quad.
    result = loading.load_image(FIXTURES / "receipt_clean.png")
    boundary = perspective.detect_document_boundary(result.image)
    assert not boundary.found
    assert boundary.corners is None


def test_correct_perspective_produces_rectangular_output():
    result = loading.load_image(FIXTURES / "receipt_on_background.png")
    boundary = perspective.detect_document_boundary(result.image)
    assert boundary.found

    corrected = perspective.correct_perspective(result.image, boundary.corners)
    assert corrected.ndim == 3
    assert corrected.shape[0] > 0
    assert corrected.shape[1] > 0
    # The corrected crop should be mostly background-free (bright/white
    # dominated), unlike the original which includes the dark backdrop.
    assert corrected.mean() > result.image.mean()


def test_detect_and_correct_falls_back_to_original_when_no_boundary():
    result = loading.load_image(FIXTURES / "receipt_clean.png")
    output = perspective.detect_and_correct(result.image)
    assert np.array_equal(output, result.image)


def test_detect_and_correct_crops_when_boundary_found():
    result = loading.load_image(FIXTURES / "receipt_on_background.png")
    output = perspective.detect_and_correct(result.image)
    assert output.shape != result.image.shape or not np.array_equal(output, result.image)


def test_order_corners_is_consistent_regardless_of_input_order():
    pts = np.array([[10, 10], [110, 10], [110, 210], [10, 210]], dtype=np.float32)
    shuffled = pts[[2, 0, 3, 1]]
    ordered_a = perspective._order_corners(pts)
    ordered_b = perspective._order_corners(shuffled)
    assert np.array_equal(ordered_a, ordered_b)

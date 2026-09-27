from pathlib import Path

import cv2

from receiptlingua.pipeline.preprocess import loading, quality
from receiptlingua.pipeline.preprocess.grayscale import to_grayscale

FIXTURES = Path(__file__).parent / "fixtures"


def test_clean_receipt_scores_as_good_quality():
    result = loading.load_image(FIXTURES / "receipt_clean.png")
    score = quality.score_quality(result.image)
    assert not score.is_low_contrast
    assert not score.is_poorly_lit
    assert not score.needs_accurate_mode


def test_low_contrast_fixture_flagged():
    result = loading.load_image(FIXTURES / "receipt_low_contrast.png")
    score = quality.score_quality(result.image)
    assert score.is_low_contrast
    assert score.needs_accurate_mode


def test_dark_fixture_flagged_poorly_lit():
    result = loading.load_image(FIXTURES / "receipt_dark.png")
    score = quality.score_quality(result.image)
    assert score.is_poorly_lit
    assert score.needs_accurate_mode


def test_blurred_fixture_flagged_blurry():
    result = loading.load_image(FIXTURES / "receipt_clean.png")
    gray = to_grayscale(result.image)
    blurred = cv2.GaussianBlur(gray, (0, 0), sigmaX=5.0)
    score = quality.score_quality(blurred)
    assert score.is_blurry
    assert score.needs_accurate_mode


def test_scores_are_finite_and_within_expected_ranges():
    result = loading.load_image(FIXTURES / "receipt_noisy.png")
    score = quality.score_quality(result.image)
    assert score.blur_score >= 0
    assert score.contrast_score >= 0
    assert 0 <= score.brightness_score <= 255

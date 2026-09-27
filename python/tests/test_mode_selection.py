"""Deterministic tests for fast/accurate/auto mode selection. No real OCR."""

from __future__ import annotations

from receiptlingua.engines.mode import LOW_CONFIDENCE_THRESHOLD, Mode, decide, should_escalate
from receiptlingua.engines.types import BBox, EngineResult, EngineTextLine
from receiptlingua.pipeline.preprocess.quality import QualityScore


def _quality(*, blurry=False, low_contrast=False, poorly_lit=False) -> QualityScore:
    return QualityScore(
        blur_score=200.0 if not blurry else 10.0,
        contrast_score=80.0 if not low_contrast else 5.0,
        brightness_score=140.0 if not poorly_lit else 5.0,
        is_blurry=blurry,
        is_low_contrast=low_contrast,
        is_poorly_lit=poorly_lit,
    )


def test_explicit_fast_mode_is_never_escalated_by_quality():
    decision = decide(Mode.FAST, _quality(blurry=True, low_contrast=True, poorly_lit=True))
    assert decision.resolved_mode == Mode.FAST


def test_explicit_accurate_mode_stays_accurate_even_on_good_quality():
    decision = decide(Mode.ACCURATE, _quality())
    assert decision.resolved_mode == Mode.ACCURATE


def test_auto_mode_resolves_to_fast_on_good_quality():
    decision = decide(Mode.AUTO, _quality())
    assert decision.resolved_mode == Mode.FAST


def test_auto_mode_resolves_to_accurate_when_blurry():
    decision = decide(Mode.AUTO, _quality(blurry=True))
    assert decision.resolved_mode == Mode.ACCURATE
    assert "blurry" in decision.reason


def test_auto_mode_resolves_to_accurate_when_low_contrast():
    decision = decide(Mode.AUTO, _quality(low_contrast=True))
    assert decision.resolved_mode == Mode.ACCURATE


def test_auto_mode_resolves_to_accurate_when_poorly_lit():
    decision = decide(Mode.AUTO, _quality(poorly_lit=True))
    assert decision.resolved_mode == Mode.ACCURATE


def _result(lines_confidences: list[float]) -> EngineResult:
    lines = tuple(
        EngineTextLine(text="x", bbox=BBox(0, 0, 1, 1), confidence=c, status="ok")
        for c in lines_confidences
    )
    return EngineResult(engine="fake", engine_version="0", text_lines=lines)


def test_fast_mode_never_escalates_regardless_of_confidence():
    assert should_escalate(Mode.FAST, _result([0.0])) is False


def test_accurate_mode_never_escalates_regardless_of_confidence():
    assert should_escalate(Mode.ACCURATE, _result([0.0])) is False


def test_auto_mode_escalates_on_empty_result():
    assert should_escalate(Mode.AUTO, _result([])) is True


def test_auto_mode_escalates_on_low_mean_confidence():
    assert should_escalate(Mode.AUTO, _result([LOW_CONFIDENCE_THRESHOLD - 0.1])) is True


def test_auto_mode_does_not_escalate_on_high_mean_confidence():
    assert should_escalate(Mode.AUTO, _result([0.95, 0.9])) is False

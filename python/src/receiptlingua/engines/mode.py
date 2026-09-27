"""Fast/accurate/auto mode-selection policy.

Sits above the :class:`~receiptlingua.engines.base.OCREngine` interface,
not inside any backend. ``auto`` mode uses the image-quality heuristic
scorer already built for preprocessing
(``receiptlingua.pipeline.preprocess.quality``) to decide whether a
second, more expensive OCR pass should run -- e.g. re-recognizing the
same image after accurate-mode preprocessing, or trying a second engine.

This module makes decisions; it does not run OCR itself. Callers wire
:func:`decide` and :func:`should_escalate` around their own engine
calls.
"""

from __future__ import annotations

from dataclasses import dataclass

from receiptlingua.engines.types import EngineResult
from receiptlingua.pipeline.preprocess.orchestrator import Mode
from receiptlingua.pipeline.preprocess.quality import QualityScore

__all__ = ["Mode", "ModeDecision", "decide", "should_escalate", "LOW_CONFIDENCE_THRESHOLD"]

# A first-pass OCR result with mean confidence below this is considered
# weak enough that ``auto`` mode should escalate to a second pass.
LOW_CONFIDENCE_THRESHOLD = 0.5


@dataclass(frozen=True)
class ModeDecision:
    resolved_mode: Mode
    reason: str


def decide(requested_mode: Mode, quality: QualityScore) -> ModeDecision:
    """Resolve ``fast``/``accurate``/``auto`` to a concrete mode for one pass.

    Deterministic given ``quality`` -- no OCR needs to run to test this.
    """
    if requested_mode == Mode.FAST:
        return ModeDecision(Mode.FAST, "explicitly requested")
    if requested_mode == Mode.ACCURATE:
        return ModeDecision(Mode.ACCURATE, "explicitly requested")

    if quality.needs_accurate_mode:
        signals = []
        if quality.is_blurry:
            signals.append("blurry")
        if quality.is_low_contrast:
            signals.append("low_contrast")
        if quality.is_poorly_lit:
            signals.append("poorly_lit")
        return ModeDecision(Mode.ACCURATE, f"auto: quality signals={','.join(signals)}")

    return ModeDecision(Mode.FAST, "auto: quality within normal range")


def _mean_confidence(result: EngineResult) -> float:
    if result.is_empty:
        return 0.0
    return sum(line.confidence for line in result.text_lines) / len(result.text_lines)


def should_escalate(requested_mode: Mode, first_pass: EngineResult) -> bool:
    """Whether ``auto`` mode should run a second, more expensive OCR pass.

    Only applies when the caller requested ``auto`` -- ``fast`` and
    ``accurate`` are single-pass by definition. Escalates when the first
    pass produced nothing, or produced text but at low mean confidence
    (the two situations a stronger preprocessing candidate or a slower
    backend configuration is meant to address).
    """
    if requested_mode != Mode.AUTO:
        return False
    if first_pass.is_empty:
        return True
    return _mean_confidence(first_pass) < LOW_CONFIDENCE_THRESHOLD

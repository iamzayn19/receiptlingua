"""Language identification on OCR'd text.

Backend: **py3langid** (MIT-licensed, actively maintained fork of the
BSD-licensed ``langid.py``), chosen over plain ``langid``/fastText's
``lid.176`` because:

- It is pure Python with its trained model bundled inside the pip
  package itself (no separate model download at runtime -- this needs to
  work fully offline immediately after ``pip install``, unlike fastText's
  ~130MB ``lid.176.bin`` which has to be fetched separately).
- It installs and imports cleanly in this environment (verified: `pip
  install py3langid` succeeds on Python 3.14, no build step).
- Its bundled model covers 142 language labels, including every
  mandatory language in this project's high-priority list (see
  ``LANGUAGES.md`` / ``langid/data/language_matrix.json``) except that it
  outputs one generic ``zh`` label rather than separate Simplified /
  Traditional Chinese labels -- noted explicitly in the matrix.

Honesty about short/unreliable text: py3langid's classifier always
returns *some* label, even for a 2-character string or a bare number --
and for such inputs its confidence is close to meaningless (verified:
``classify("hi")`` and ``classify("42")`` both score an unrelated
language at ~0.01 normalized confidence). This module enforces both a
minimum text length AND a minimum confidence before returning a real
code; anything short of both thresholds returns ``"unknown"`` rather
than a fabricated confident guess. This matters directly for receipts,
which are full of short lines: product codes, quantities, currency
symbols, single-word units.
"""

from __future__ import annotations

from dataclasses import dataclass

from py3langid.langid import MODEL_FILE, LanguageIdentifier

#: Below this many stripped characters, language ID is not attempted at all.
DEFAULT_MIN_TEXT_LENGTH = 8

#: Below this normalized confidence (0..1), the result is reported as unknown.
DEFAULT_MIN_CONFIDENCE = 0.5

UNKNOWN = "unknown"

_identifier: LanguageIdentifier | None = None


def _get_identifier() -> LanguageIdentifier:
    global _identifier
    if _identifier is None:
        # norm_probs=True turns raw log-likelihoods into a real 0..1
        # confidence (verified: without it, `classify()` returns huge
        # negative log-likelihood numbers, not something threshold-able).
        _identifier = LanguageIdentifier.from_model_file(MODEL_FILE, norm_probs=True)
    return _identifier


@dataclass(frozen=True)
class LanguageGuess:
    """One language guess. ``code`` is a py3langid label or "unknown"."""

    code: str
    confidence: float


def supported_language_codes() -> frozenset[str]:
    """The full set of language labels this backend's model can output."""
    return frozenset(_get_identifier().nb_classes)


def identify_text(
    text: str,
    *,
    min_text_length: int = DEFAULT_MIN_TEXT_LENGTH,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> LanguageGuess:
    """Identify the language of one string of OCR'd text (e.g. one line).

    Returns ``LanguageGuess("unknown", 0.0)`` when the stripped text is
    shorter than ``min_text_length`` or the model's own normalized
    confidence is below ``min_confidence`` -- never a confident-looking
    guess on input too short/unreliable to support one.
    """
    stripped = text.strip()
    if len(stripped) < min_text_length:
        return LanguageGuess(UNKNOWN, 0.0)

    code, prob = _get_identifier().classify(stripped)
    prob = float(prob)
    if prob < min_confidence:
        return LanguageGuess(UNKNOWN, 0.0)
    return LanguageGuess(code, prob)


def rank_text(
    text: str, *, min_text_length: int = DEFAULT_MIN_TEXT_LENGTH
) -> list[LanguageGuess]:
    """Full ranked list of language guesses for ``text``, most likely first.

    Unlike :func:`identify_text`, this does not apply the confidence
    floor -- it exists for document-level aggregation (see
    ``langid.tagging``), where even a single line's low-confidence
    distribution can contribute a useful, appropriately-small vote.
    Still returns ``[]`` for text shorter than ``min_text_length``, since
    there is nothing honest to rank below that.
    """
    stripped = text.strip()
    if len(stripped) < min_text_length:
        return []
    ranked = _get_identifier().rank(stripped)
    return [LanguageGuess(code, float(prob)) for code, prob in ranked]

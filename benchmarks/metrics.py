"""Real evaluation metrics for the OCR benchmark harness.

No external Levenshtein dependency: ``python-Levenshtein``/``Levenshtein``
are not installed in this environment, and pulling in a new (partially
C-extension) dependency just for this wasn't worth it for a
straightforward O(n*m) DP edit distance. ``_edit_distance`` below is a
plain, correct implementation, unit-tested against known cases in
``python/tests/test_benchmark_metrics.py``.
"""

from __future__ import annotations

from dataclasses import dataclass


def _edit_distance(a: list[str] | str, b: list[str] | str) -> int:
    """Levenshtein edit distance over a sequence of tokens or characters."""
    n, m = len(a), len(b)
    if n == 0:
        return m
    if m == 0:
        return n
    prev = list(range(m + 1))
    for i in range(1, n + 1):
        curr = [i] + [0] * m
        ai = a[i - 1]
        for j in range(1, m + 1):
            cost = 0 if ai == b[j - 1] else 1
            curr[j] = min(
                prev[j] + 1,  # deletion
                curr[j - 1] + 1,  # insertion
                prev[j - 1] + cost,  # substitution
            )
        prev = curr
    return prev[m]


def character_error_rate(reference: str, hypothesis: str) -> float:
    """CER = edit_distance(chars) / len(reference chars). 0.0 for an empty
    reference and empty hypothesis; 1.0 (capped) style values above 1 are
    left uncapped since insertions can exceed reference length -- this is
    the standard definition, not artificially clamped."""
    if len(reference) == 0:
        return 0.0 if len(hypothesis) == 0 else 1.0
    return _edit_distance(reference, hypothesis) / len(reference)


def word_error_rate(reference: str, hypothesis: str) -> float:
    ref_words = reference.split()
    hyp_words = hypothesis.split()
    if len(ref_words) == 0:
        return 0.0 if len(hyp_words) == 0 else 1.0
    return _edit_distance(ref_words, hyp_words) / len(ref_words)


def normalized_edit_distance(reference: str, hypothesis: str) -> float:
    """Edit distance normalized by max(len(reference), len(hypothesis), 1)
    -- always in [0, 1], unlike CER which can exceed 1."""
    denom = max(len(reference), len(hypothesis), 1)
    return _edit_distance(reference, hypothesis) / denom


def fuzzy_match(a: str, b: str, *, threshold: float = 0.8) -> bool:
    """True if the normalized similarity (1 - normalized edit distance)
    between two strings meets ``threshold``. Case-insensitive, whitespace-
    trimmed -- used for merchant-name matching, which per the ADRs is a
    known-weak heuristic where exact match is too strict to be useful
    signal."""
    a_n, b_n = a.strip().lower(), b.strip().lower()
    if not a_n and not b_n:
        return True
    similarity = 1.0 - normalized_edit_distance(a_n, b_n)
    return similarity >= threshold


@dataclass(frozen=True)
class CaseMetrics:
    cer: float
    wer: float
    normalized_edit_distance: float
    merchant_match: bool | None  # None if ground truth had no merchant to compare
    date_exact_match: bool | None
    total_exact_match: bool | None

    def to_dict(self) -> dict:
        return {
            "cer": self.cer,
            "wer": self.wer,
            "normalized_edit_distance": self.normalized_edit_distance,
            "merchant_match": self.merchant_match,
            "date_exact_match": self.date_exact_match,
            "total_exact_match": self.total_exact_match,
        }

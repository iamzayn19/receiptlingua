"""Language ID on real short vs. long strings -- verifies the honest
"unknown" fallback for input too short/unreliable to support a real
confident guess, per the project's "never fabricate certainty" rule.
"""

from __future__ import annotations

from receiptlingua.langid.identify import (
    UNKNOWN,
    identify_text,
    rank_text,
    supported_language_codes,
)


def test_long_confident_english_text_is_identified():
    text = "The quick brown fox jumps over the lazy dog near the corner store"
    guess = identify_text(text)
    assert guess.code == "en"
    assert guess.confidence > 0.5


def test_long_confident_french_text_is_identified():
    text = "Bonjour tout le monde, comment allez-vous aujourd'hui"
    guess = identify_text(text)
    assert guess.code == "fr"
    assert guess.confidence > 0.5


def test_short_string_returns_unknown_not_a_fabricated_guess():
    for short in ("hi", "ok", "42", "$5"):
        guess = identify_text(short)
        assert guess.code == UNKNOWN
        assert guess.confidence == 0.0


def test_bare_number_returns_unknown():
    guess = identify_text("3.49")
    assert guess.code == UNKNOWN


def test_empty_and_whitespace_only_return_unknown():
    assert identify_text("").code == UNKNOWN
    assert identify_text("   ").code == UNKNOWN


def test_min_text_length_is_configurable():
    text = "Bonjour le monde"  # 16 chars
    assert identify_text(text, min_text_length=100).code == UNKNOWN
    assert identify_text(text, min_text_length=5).code != UNKNOWN


def test_min_confidence_is_configurable():
    text = "The quick brown fox jumps over the lazy dog"
    # An unreasonably high confidence floor should force "unknown" even
    # for text that's normally identified confidently.
    guess = identify_text(text, min_confidence=0.999999)
    assert guess.code == UNKNOWN


def test_rank_text_returns_full_distribution_for_long_text():
    text = "Bonjour tout le monde, comment allez-vous aujourd'hui"
    ranked = rank_text(text)
    assert len(ranked) > 1
    assert ranked[0].code == "fr"
    # Ranked list should be sorted descending by confidence.
    for a, b in zip(ranked, ranked[1:], strict=False):
        assert a.confidence >= b.confidence


def test_rank_text_returns_empty_for_short_text():
    assert rank_text("hi") == []


def test_supported_language_codes_covers_mandatory_languages():
    codes = supported_language_codes()
    # Every mandatory language except the two Chinese variants (py3langid
    # only has one generic "zh" label, documented in the language matrix).
    for code in (
        "en", "ur", "ar", "hi", "ta", "te", "bn", "pa", "gu", "kn", "ml", "mr",
        "ne", "fa", "zh", "ja", "ko", "th", "id", "ms", "vi", "fr", "de", "es",
        "pt", "it", "nl", "tr", "ru", "uk", "pl",
    ):
        assert code in codes

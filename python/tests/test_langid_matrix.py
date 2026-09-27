"""Matrix-loading tests for the language capability table."""

from __future__ import annotations

from receiptlingua.langid.matrix import (
    load_matrix,
    model_supported_languages,
    receipt_verified_languages,
)

MANDATORY_CODES = {
    "en", "ur", "ar", "hi", "ta", "te", "bn", "pa", "gu", "kn", "ml", "mr", "ne",
    "fa", "zh-Hans", "zh-Hant", "ja", "ko", "th", "id", "ms", "vi", "fr", "de",
    "es", "pt", "it", "nl", "tr", "ru", "uk", "pl",
}


def test_matrix_loads_and_has_entries():
    entries = load_matrix()
    assert len(entries) > 0
    assert all(hasattr(e, "code") and hasattr(e, "model_supported") for e in entries)


def test_matrix_has_no_duplicate_codes():
    entries = load_matrix()
    codes = [e.code for e in entries]
    assert len(codes) == len(set(codes))


def test_all_mandatory_languages_present():
    entries = load_matrix()
    codes = {e.code for e in entries}
    missing = MANDATORY_CODES - codes
    assert not missing, f"missing mandatory languages: {missing}"


def test_all_mandatory_languages_are_model_supported():
    entries = {e.code: e for e in load_matrix()}
    for code in MANDATORY_CODES:
        assert entries[code].model_supported, f"{code} should be model_supported"


def test_no_language_is_receipt_verified_yet():
    # Non-negotiable: no receipt benchmark exists yet (milestone 171-185),
    # so nothing should be marked receipt_verified=True right now.
    assert receipt_verified_languages() == ()
    for entry in load_matrix():
        assert entry.receipt_verified is False


def test_model_supported_languages_is_a_strict_subset():
    all_entries = load_matrix()
    supported = model_supported_languages()
    assert len(supported) <= len(all_entries)
    assert all(e.model_supported for e in supported)
    assert any(not e.model_supported for e in all_entries), (
        "expected at least one honestly-unsupported entry (not everything "
        "should be marked supported)"
    )


def test_every_entry_has_nonempty_notes_explaining_its_status():
    for entry in load_matrix():
        assert entry.notes and len(entry.notes) > 0

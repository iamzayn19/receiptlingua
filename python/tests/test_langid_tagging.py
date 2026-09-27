"""Per-line and document-level tagging tests (mixed-language documents)."""

from __future__ import annotations

from receiptlingua.langid.tagging import tag_document, tag_line


def test_tag_line_english():
    tag = tag_line("The quick brown fox jumps over the lazy dog")
    assert "Latn" in tag.scripts
    assert tag.language.code == "en"


def test_tag_line_short_line_is_unknown_language_but_still_has_script():
    tag = tag_line("MILK 3.49")
    assert tag.scripts == ("Latn",)
    assert tag.language.code == "unknown"


def test_tag_document_mixed_language_receipt():
    lines = [
        "CORNER STORE",
        "The quick brown fox jumps over the lazy dog near the store",
        "Bonjour tout le monde, comment allez-vous aujourd'hui",
        "TOTAL 6.48",
    ]
    doc = tag_document(lines)
    codes = [entry["code"] for entry in doc.languages]
    assert "en" in codes
    assert "fr" in codes
    assert "Latn" in doc.scripts
    # Confidences should sum to ~1 (normalized vote).
    assert abs(sum(entry["confidence"] for entry in doc.languages) - 1.0) < 1e-3


def test_tag_document_scripts_ordered_by_character_count():
    lines = [
        "பிரைஸ் பட்டியல்",  # Tamil, longer
        "OK",  # tiny Latin
    ]
    doc = tag_document(lines)
    assert doc.scripts[0] == "Taml"


def test_tag_document_all_short_lines_yields_no_confident_languages():
    lines = ["OK", "42", "$5", "x1"]
    doc = tag_document(lines)
    assert doc.languages == ()


def test_tag_document_line_tags_preserve_order_and_count():
    lines = ["one", "two", "three"]
    doc = tag_document(lines)
    assert [t.text for t in doc.line_tags] == lines

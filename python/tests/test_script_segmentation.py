"""Real mixed-script Unicode test strings, not synthetic placeholders."""

from __future__ import annotations

from receiptlingua.langid.script import char_script, dominant_scripts, segment_scripts


def test_pure_latin_text_is_one_run():
    runs = segment_scripts("CORNER STORE")
    assert len(runs) == 1
    assert runs[0].script == "Latn"
    assert runs[0].text == "CORNER STORE"


def test_pure_arabic_text_is_one_run():
    text = "فاتورة المحل"
    runs = segment_scripts(text)
    assert len(runs) == 1
    assert runs[0].script == "Arab"


def test_pure_tamil_text_is_one_run():
    text = "பிரைஸ் பட்டியல்"
    runs = segment_scripts(text)
    assert len(runs) == 1
    assert runs[0].script == "Taml"


def test_mixed_arabic_and_english_line():
    # A real bilingual receipt-style line: Arabic label + English brand name.
    text = "فاتورة CORNER STORE"
    runs = segment_scripts(text)
    scripts_seen = {r.script for r in runs}
    assert "Arab" in scripts_seen
    assert "Latn" in scripts_seen
    assert dominant_scripts(text)[0] in ("Arab", "Latn")


def test_mixed_tamil_and_english_line():
    text = "மோத TOTAL 100"
    runs = segment_scripts(text)
    scripts_seen = {r.script for r in runs}
    assert "Taml" in scripts_seen
    assert "Latn" in scripts_seen


def test_common_digits_and_punctuation_attach_to_surrounding_script():
    # "MILK 3.49" should not fragment into Latin/Common/Latin.
    runs = segment_scripts("MILK 3.49")
    assert len(runs) == 1
    assert runs[0].script == "Latn"


def test_pure_numeric_text_stays_common():
    runs = segment_scripts("123.45")
    assert len(runs) == 1
    assert runs[0].script == "Zyyy"
    assert dominant_scripts("123.45") == []


def test_cjk_scripts_distinguished():
    assert char_script("中") == "Hani"  # Han (Chinese)
    assert char_script("あ") == "Hira"  # Hiragana (Japanese)
    assert char_script("ア") == "Kana"  # Katakana (Japanese)
    assert char_script("가") == "Hang"  # Hangul (Korean)


def test_devanagari_and_cyrillic():
    assert char_script("क") == "Deva"
    assert char_script("Б") == "Cyrl"


def test_empty_string_has_no_runs():
    assert segment_scripts("") == []


def test_dominant_scripts_orders_by_character_count():
    # Mostly Tamil, a little English.
    text = "பிரைஸ் பட்டியல் மோத TOTAL"
    dominant = dominant_scripts(text)
    assert dominant[0] == "Taml"

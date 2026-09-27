"""Unicode script segmentation.

Python's stdlib ``unicodedata`` has no direct "what Unicode script is this
character" query (it exposes category, not script). The ``regex`` package
(a real, actively-maintained, permissively-licensed drop-in replacement
for ``re`` -- verified installable in this environment) supports
``\\p{Script=...}`` property matching against Unicode's actual script
database, so it is used here instead of vendoring a script-ranges table
by hand.

This module classifies each character into an ISO 15924 four-letter
script code, treating Unicode's "Common" and "Inherited" script values
(digits, punctuation, whitespace, combining marks) as script-neutral: they
are folded into whichever real-script run they sit inside, rather than
fragmenting e.g. "MILK 3.49" into separate Latin/Common/Latin runs.
"""

from __future__ import annotations

from dataclasses import dataclass

import regex

# Unicode script name (as used by \p{Script=...}) -> ISO 15924 code.
# Limited to scripts relevant to the mandatory language list (see
# LANGUAGES.md) plus other scripts commonly seen in receipts/OCR output.
# A character whose script isn't in this table is tagged "Zzzz" (unknown)
# rather than silently mis-tagged as some other script.
SCRIPT_TO_ISO15924 = {
    "Latin": "Latn",
    "Arabic": "Arab",
    "Devanagari": "Deva",
    "Tamil": "Taml",
    "Telugu": "Telu",
    "Bengali": "Beng",
    "Gurmukhi": "Guru",
    "Gujarati": "Gujr",
    "Kannada": "Knda",
    "Malayalam": "Mlym",
    "Oriya": "Orya",
    "Sinhala": "Sinh",
    "Han": "Hani",
    "Hiragana": "Hira",
    "Katakana": "Kana",
    "Hangul": "Hang",
    "Thai": "Thai",
    "Lao": "Laoo",
    "Myanmar": "Mymr",
    "Khmer": "Khmr",
    "Tibetan": "Tibt",
    "Cyrillic": "Cyrl",
    "Greek": "Grek",
    "Hebrew": "Hebr",
    "Armenian": "Armn",
    "Georgian": "Geor",
    "Ethiopic": "Ethi",
    "Thaana": "Thaa",
    "Cherokee": "Cher",
    "Canadian_Aboriginal": "Cans",
}

UNKNOWN_SCRIPT = "Zzzz"
COMMON_SCRIPT = "Zyyy"

_PATTERNS = {name: regex.compile(rf"\p{{Script={name}}}") for name in SCRIPT_TO_ISO15924}
_COMMON_PATTERN = regex.compile(r"[\p{Script=Common}\p{Script=Inherited}]")


def char_script(ch: str) -> str:
    """Return the ISO 15924 code for a single character (or Zyyy/Zzzz)."""
    if not ch or not ch.strip():
        return COMMON_SCRIPT
    if _COMMON_PATTERN.match(ch):
        return COMMON_SCRIPT
    for name, pattern in _PATTERNS.items():
        if pattern.match(ch):
            return SCRIPT_TO_ISO15924[name]
    return UNKNOWN_SCRIPT


@dataclass(frozen=True)
class ScriptRun:
    """A contiguous run of text tagged with one script."""

    text: str
    script: str
    start: int
    end: int


def segment_scripts(text: str) -> list[ScriptRun]:
    """Split ``text`` into contiguous runs of the same script.

    Common/Inherited characters (digits, spaces, punctuation) are attached
    to the nearest real-script run rather than starting runs of their own:
    a leading or trailing common-only stretch borrows the script of
    whichever real-script run is closest (preceding one preferred; the
    next one if there is no preceding run yet). Text with no real-script
    characters at all (e.g. "123.45") stays tagged Common throughout.
    """
    if not text:
        return []

    raw = [char_script(ch) for ch in text]
    labels = list(raw)

    last_real: str | None = None
    for i, s in enumerate(raw):
        if s == COMMON_SCRIPT:
            if last_real is not None:
                labels[i] = last_real
        else:
            last_real = s

    next_real: str | None = None
    for i in range(len(labels) - 1, -1, -1):
        if raw[i] != COMMON_SCRIPT:
            next_real = raw[i]
        elif labels[i] == COMMON_SCRIPT:
            labels[i] = next_real if next_real is not None else COMMON_SCRIPT

    runs: list[ScriptRun] = []
    start = 0
    for i in range(1, len(labels) + 1):
        if i == len(labels) or labels[i] != labels[start]:
            runs.append(ScriptRun(text=text[start:i], script=labels[start], start=start, end=i))
            start = i
    return runs


def dominant_scripts(text: str, *, min_run_length: int = 1) -> list[str]:
    """Distinct non-common, non-unknown ISO 15924 codes in ``text``.

    Ordered by total character count across all runs, descending, so the
    first entry is the script that makes up the most of the string.
    """
    counts: dict[str, int] = {}
    for run in segment_scripts(text):
        if run.script in (COMMON_SCRIPT, UNKNOWN_SCRIPT):
            continue
        if len(run.text) < min_run_length:
            continue
        counts[run.script] = counts.get(run.script, 0) + len(run.text)
    return [s for s, _ in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)]

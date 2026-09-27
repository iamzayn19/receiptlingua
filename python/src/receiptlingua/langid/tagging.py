"""Per-line and document-level language/script tagging.

Combines ``langid.script`` (Unicode script segmentation) and
``langid.identify`` (language ID) into output shaped exactly like the
``languages``/``scripts`` fields of
``protocol/schema/response.schema.json``:

- ``languages``: ``[{"code": ..., "confidence": ...}, ...]``, most
  confident first.
- ``scripts``: a list of ISO 15924 four-letter codes.

Supports mixed-language/mixed-script documents by tagging each line
independently first, then aggregating: script totals are summed by
character count across the whole document, and language confidence is a
normalized, confidence-weighted vote across every line's full ranked
distribution (not just each line's single top guess) so more than one
language can surface as a real candidate for genuinely mixed documents,
rather than only ever reporting the single most common line's language.
"""

from __future__ import annotations

from dataclasses import dataclass

from receiptlingua.langid.identify import LanguageGuess, identify_text, rank_text
from receiptlingua.langid.script import (
    COMMON_SCRIPT,
    UNKNOWN_SCRIPT,
    dominant_scripts,
    segment_scripts,
)


@dataclass(frozen=True)
class LineTag:
    """Script(s) and language guess for one line of OCR'd text."""

    text: str
    scripts: tuple[str, ...]
    language: LanguageGuess


def tag_line(text: str) -> LineTag:
    """Tag a single line with its dominant script(s) and language guess."""
    return LineTag(
        text=text,
        scripts=tuple(dominant_scripts(text)),
        language=identify_text(text),
    )


@dataclass(frozen=True)
class DocumentTags:
    """Document-level aggregation, shaped for the response schema."""

    languages: tuple[dict, ...]
    scripts: tuple[str, ...]
    line_tags: tuple[LineTag, ...]


def _script_char_counts(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for run in segment_scripts(text):
        if run.script in (COMMON_SCRIPT, UNKNOWN_SCRIPT):
            continue
        counts[run.script] = counts.get(run.script, 0) + len(run.text)
    return counts


def tag_document(lines: list[str]) -> DocumentTags:
    """Tag every line, then aggregate to document-level languages/scripts."""
    line_tags = tuple(tag_line(line) for line in lines)

    script_counts: dict[str, int] = {}
    for line in lines:
        for script, count in _script_char_counts(line).items():
            script_counts[script] = script_counts.get(script, 0) + count
    scripts = tuple(s for s, _ in sorted(script_counts.items(), key=lambda kv: kv[1], reverse=True))

    lang_scores: dict[str, float] = {}
    for line in lines:
        for guess in rank_text(line):
            lang_scores[guess.code] = lang_scores.get(guess.code, 0.0) + guess.confidence

    total = sum(lang_scores.values())
    languages: list[dict] = []
    if total > 0:
        for code, score in sorted(lang_scores.items(), key=lambda kv: kv[1], reverse=True):
            languages.append({"code": code, "confidence": round(score / total, 4)})

    return DocumentTags(languages=tuple(languages), scripts=scripts, line_tags=line_tags)

"""Loader for the language capability matrix.

The matrix (``data/language_matrix.json``) is the single source of truth
for two deliberately separate concepts, per the project's non-negotiable
design requirement:

- ``model_supported``: the backend stack can *technically* produce output
  for this language right now -- verified against both a real language ID
  label (py3langid's bundled model) and a real OCR backend's documented
  language pack (Tesseract's ``tessdata_fast`` distribution), not
  aspirational.
- ``receipt_verified``: there is benchmark evidence this works well on
  actual receipts. No receipt benchmark exists yet (that is milestone
  171-185), so this is ``False`` for every single entry right now --
  never fabricated as ``True`` ahead of real evidence.

``LANGUAGES.md`` at the repo root is a generated, human-readable view of
this same file (see ``python/scripts/generate_languages_md.py``); the
JSON file here is what code should load, not the Markdown.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_DATA_PATH = Path(__file__).parent / "data" / "language_matrix.json"


@dataclass(frozen=True)
class LanguageEntry:
    code: str
    name: str
    script: str
    model_supported: bool
    receipt_verified: bool
    rtl: bool
    mandatory: bool
    notes: str


def load_matrix(path: Path | None = None) -> tuple[LanguageEntry, ...]:
    """Load the language capability matrix from its JSON data file."""
    data = json.loads((path or _DATA_PATH).read_text(encoding="utf-8"))
    return tuple(LanguageEntry(**entry) for entry in data)


def model_supported_languages(path: Path | None = None) -> tuple[LanguageEntry, ...]:
    """Entries with ``model_supported=True``."""
    return tuple(e for e in load_matrix(path) if e.model_supported)


def receipt_verified_languages(path: Path | None = None) -> tuple[LanguageEntry, ...]:
    """Entries with ``receipt_verified=True``.

    Expected to be empty until milestone 171-185 (receipt benchmarking)
    produces real evidence -- an empty result here is correct, not a bug.
    """
    return tuple(e for e in load_matrix(path) if e.receipt_verified)

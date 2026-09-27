#!/usr/bin/env python3
"""Regenerate LANGUAGES.md at the repo root from langid/data/language_matrix.json.

Run after editing the matrix JSON so the human-readable doc stays in sync:

    python3 python/scripts/generate_languages_md.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "python" / "src"))

from receiptlingua.langid.matrix import load_matrix  # noqa: E402

OUTPUT_PATH = REPO_ROOT / "LANGUAGES.md"

HEADER = """# Language support matrix

This file is generated from
[`python/src/receiptlingua/langid/data/language_matrix.json`](python/src/receiptlingua/langid/data/language_matrix.json)
by `python/scripts/generate_languages_md.py`. Edit the JSON, then re-run
that script -- don't hand-edit the table below, it will be overwritten.

## Two separate concepts (read this before the table)

This project tracks two deliberately different things per language, and
they must never be conflated:

- **`model_supported`**: the backend stack can *technically* produce
  output for this language right now. This is checked against real,
  verified capability: does [py3langid](https://pypi.org/project/py3langid/)'s
  bundled language ID model have a label for it, **and** does
  [Tesseract](https://github.com/tesseract-ocr/tessdata_fast) have a
  documented trained-data language pack for it. Both must be true.
- **`receipt_verified`**: there is real benchmark evidence this
  language/script combination works well specifically *on receipts*
  (thermal-printer fonts, low-quality photos, receipt layouts) -- not
  just on the general-purpose text these backends/models were originally
  trained on.

**As of this milestone (81-100), there is no receipt benchmark yet**
(that is a later milestone, 171-185). So every single row below has
`receipt_verified = false`, honestly, regardless of how well-supported
the language otherwise looks. A `true` here will only ever appear once a
real benchmark has produced real evidence -- never as a placeholder or
aspiration.

There is a **third, separate concept** this table does not track:
whether `python/src/receiptlingua/synth/generator.py` (the synthetic
receipt generator used to produce training/eval fixtures) can actually
render a language. That module has its own, narrower gate -- a language
is added there only once a real font file on the running machine is
bbox-probed (`PIL.ImageFont.getmask(ch).getbbox()`) to render genuine,
non-`.notdef` glyphs for that script, *and* the author has vocabulary
they are confident is real and correctly spelled. As of the language-
expansion pass in `docs/COMMIT_PLAN.md`, the synth generator supports 25
languages this way; several more (Telugu, Bengali, Punjabi, Gujarati,
Kannada, Malayalam, Nepali, Thai) have a verified font on this machine
but were left out for lack of confident vocabulary -- see that doc for
the full list. A synth-generator font pass being verified is **not**
the same as `receipt_verified` above, which requires actual benchmark
evidence, not just a working font -- do not conflate the two.

## Coverage summary

"""


def _bool_cell(value: bool) -> str:
    return "Yes" if value else "No"


def render() -> str:
    entries = load_matrix()
    total = len(entries)
    supported = sum(1 for e in entries if e.model_supported)
    verified = sum(1 for e in entries if e.receipt_verified)
    mandatory = [e for e in entries if e.mandatory]
    mandatory_supported = sum(1 for e in mandatory if e.model_supported)

    lines = [HEADER]
    lines.append(
        f"- **{supported} / {total}** entries are `model_supported = true` right now.\n"
        f"- **{mandatory_supported} / {len(mandatory)}** of the project's mandatory "
        "high-priority languages are `model_supported = true` (all of them, as of "
        f"this milestone -- see notes below on why the *rest* of the {total} aren't).\n"
        f"- **{verified} / {total}** are `receipt_verified = true` (expected: zero, "
        "no receipt benchmark exists yet).\n"
    )
    lines.append(
        "The gap between `model_supported` and the aspirational ~109-language target "
        "is **not a hard ceiling** -- it reflects which Tesseract language packs "
        "(`.traineddata` files) are actually installed in a given checkout right "
        "now (only `eng` ships by default in this environment) versus which ones "
        "Tesseract's `tessdata_fast` distribution documents as available. Installing "
        "more packs (`brew install tesseract-lang` for the full set, or fetching "
        "individual `.traineddata` files) is a coverage-expansion task for later, "
        "not something blocked on code here. A handful of entries are marked "
        "`model_supported = false` for a *different*, real reason: py3langid's "
        "142-label model has no language ID label for them (e.g. Tibetan, Dhivehi, "
        "Tigrinya) or no Tesseract pack exists for them at all -- see each row's "
        "notes.\n"
    )

    lines.append("## Mandatory high-priority languages\n")
    lines.append("| Code | Name | Script | RTL | Model supported | Receipt verified | Notes |")
    lines.append("|---|---|---|---|---|---|---|")
    for e in mandatory:
        lines.append(
            f"| `{e.code}` | {e.name} | {e.script} | {_bool_cell(e.rtl)} | "
            f"{_bool_cell(e.model_supported)} | {_bool_cell(e.receipt_verified)} | {e.notes} |"
        )

    lines.append("\n## Additional languages\n")
    lines.append("| Code | Name | Script | RTL | Model supported | Receipt verified | Notes |")
    lines.append("|---|---|---|---|---|---|---|")
    for e in entries:
        if e.mandatory:
            continue
        lines.append(
            f"| `{e.code}` | {e.name} | {e.script} | {_bool_cell(e.rtl)} | "
            f"{_bool_cell(e.model_supported)} | {_bool_cell(e.receipt_verified)} | {e.notes} |"
        )

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    OUTPUT_PATH.write_text(render(), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

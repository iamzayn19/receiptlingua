# Commit Plan (target: ~200 atomic commits)

This plan is directional, not a rigid script. Commits will be added, split, or
merged as implementation reveals better boundaries; this file is updated as
that happens rather than followed blindly.

## 1-15 Bootstrap
1. chore: initialize monorepo skeleton
2. docs: add feasibility note (ADR 0001)
3. docs: add commit plan
4. chore: add LICENSE (Apache-2.0)
5. chore: add NOTICE
6. docs: add README skeleton
7. docs: add CONTRIBUTING
8. docs: add CODE_OF_CONDUCT
9. docs: add SECURITY policy
10. docs: add SUPPORT
11. docs: add ROADMAP
12. docs: add ARCHITECTURE overview
13. chore: add .gitignore for python/js/ruby/models/datasets
14. chore: add EditorConfig and base lint configs
15. chore: add FUNDING.yml placeholder (no identifiers yet)

## 16-30 Protocol/schema
16-30. Define JSON schema_version 0.1, request/response envelope, error codes,
language/script objects, box/polygon types, protocol conformance fixtures,
protocol README, versioning policy.

## 31-55 Preprocessing
31-55. Image loading/validation, EXIF normalization, orientation detection,
document boundary detection, perspective correction, deskew, CLAHE,
adaptive threshold, denoise, sharpen, gamma/illumination correction,
quality-heuristic scorer, candidate pipeline orchestration, unit tests per
stage.

## 56-80 OCR engine abstraction
56-80. Engine interface, PaddleOCR backend adapter, Tesseract fallback
adapter, Surya benchmark-only adapter, fast/accurate/auto mode selection,
model download/cache manager, offline error handling, backend capability
probing (MPS/CPU/CUDA), batching support.

## 81-100 Language/script detection
81-100. Unicode script segmentation, line/region-level script tagging,
language ID integration, mixed-script/RTL handling, confidence thresholds,
model_supported vs receipt_verified matrix generation.

## 101-120 Structured receipt extraction
101-120. Reading-order reconstruction, merchant/date/time/currency/total
extraction rules, line-item table extraction, evidence/provenance linking,
uncertain/illegible/truncated/missing_region field states.

## 121-140 Python packaging/CLI
121-140. `receiptlingua` package layout, `ReceiptOCR` API, CLI (`scan`,
`languages`, `models`, `doctor`, `benchmark`, `cache info`), pyproject/uv
setup, ruff/mypy/pytest wiring, packaging smoke tests.

## 141-155 JavaScript client
141-155. TypeScript client package, sidecar process manager, protocol
client, vitest suite, eslint/prettier config, npm packaging.

## 156-170 Ruby client
156-170. Gem structure, sidecar client, RSpec suite, rubocop config,
gemspec, packaging.

## 171-185 Datasets/benchmarking
171-185. `datasets/registry.yaml`, license-audited downloader scripts,
synthetic receipt generator, deterministic corruption pipeline, benchmark
harness, CER/WER/field-accuracy metrics, BENCHMARKS.md report generation.

## 186-195 Website/docs/security/release automation
186-195. GitHub Pages site, LANGUAGES.md matrix page, CI workflows
(python/node/ruby/lint/security), SBOM generation, Dependabot config,
release workflow drafts (no auto-publish yet).

## 196-200 Release hardening
196-200. Cross-language conformance test run, offline-mode validation,
first real tagged pre-release, final README pass, blockers doc for
owner-only actions (npm login, gem signin, GitHub repo creation confirm).

---

Status: commits 1-15 done; 16-30 (protocol/schema) done as of 2026-09-27.
Actual commit count for 16-30 was ~11 rather than 15, since the schema work
naturally grouped into fewer, larger atomic steps (envelope, languages,
text lines, structured fields, error schema, versioning, script, and one
commit per fixture). Transport mechanism (stdio vs. Unix socket) remains
an open question for a future ADR before milestone 31+ needs it directly,
and is not blocking — the sidecar isn't implemented yet.

31-55 (preprocessing) done as of 2026-09-27, in ~12 commits rather than the
~25 implied by the range (each stage plus its tests landed as one atomic
commit, and fixture generation/plan scaffolding were grouped rather than
split further). This is also the first code under `python/`, so minimal
packaging scaffolding was added alongside it (not the full 121-140
packaging/CLI milestone): `python/pyproject.toml`, a `src/receiptlingua`
layout, ruff+pytest config. Dependencies chosen: numpy, pillow, and
opencv-python-headless (all BSD/permissive-licensed, verified installable
in this environment on Python 3.14). `uv` was checked again and is still
not installed, so plain `venv`+`pip` was used.

Implemented under `python/receiptlingua/pipeline/preprocess/`: image
loading/validation (decompression-bomb and malformed-file guards), EXIF
orientation normalization, deskew, a v0 heuristic perspective/document-
boundary correction (documented as a simplified approach, not a trained
model), grayscale normalization, CLAHE, adaptive thresholding, fast/
accurate denoising, unsharp-mask sharpening, gamma/illumination
correction, an image-quality heuristic scorer (blur/contrast/brightness),
and a pipeline orchestrator that gates accurate-mode stages on the
quality score instead of always running every technique. 74 tests pass
against synthetic fixtures generated in-repo (no downloaded photos),
including corrupt/zero-byte/non-image/decompression-bomb edge cases.

Deviation: adaptive thresholding and denoise/sharpen are implemented as
standalone, independently testable modules but are not both wired into
the orchestrator's default candidate (thresholding is left for the OCR
engine layer to invoke per-backend, since some OCR backends prefer
grayscale input over a hard binary mask). Open question for a future ADR:
whether the v0 perspective-correction heuristic needs to be replaced by a
trained document-boundary model once real-world (non-synthetic) receipt
photos are available to benchmark against.

56-80 (OCR engine abstraction) done as of 2026-09-27, in ~14 commits.
Implemented under `python/receiptlingua/engines/`: an abstract
`OCREngine` interface (`base.py`) mapping cleanly onto
`protocol/schema/response.schema.json`'s `text_line`/`word`/
`recognition_status` vocabulary (`types.py`); protocol-aligned error
types matching `error.schema.json`'s error code enum exactly
(`errors.py`); an offline model/language-data cache manager respecting
`RECEIPTLINGUA_CACHE_DIR` (falling back to `$XDG_CACHE_HOME` then
`~/.cache/receiptlingua`) that raises `MODEL_NOT_FOUND` rather than
downloading anything (`cache.py`); backend capability probing
(`capabilities.py`); a fast/accurate/auto mode-selection policy layer
built on the existing image-quality heuristic scorer (`mode.py`); an
engine registry/factory preferring PaddleOCR then falling back to
Tesseract (`registry.py`); a real, working `TesseractEngine` adapter
using `pytesseract`, with PSM 6 tuned for receipt-shaped images
(`tesseract_engine.py`); and a real, working `PaddleOCREngine` adapter
(`paddleocr_engine.py`) -- see below.

**Follow-up (same day): PaddleOCR gap closed via a Python 3.13 sidecar.**
The original blocker (`paddlepaddle` ships no Python 3.14 wheel) was an
interpreter-version gap, not a platform one, so it was closed by pinning
a separate `python3.13` venv (`.venv-paddle/`, gitignored, Homebrew
Python 3.13.9) with real `paddlepaddle==3.3.1` + `paddleocr==3.7.0`
installed, and running PaddleOCR as a subprocess sidecar from the main
Python 3.14 process (`receiptlingua.engines._paddle_sidecar_script`,
invoked via the new `RECEIPTLINGUA_PADDLE_PYTHON` env var). Real smoke
tests against the existing English/Tamil/Arabic fixtures show English
recognized perfectly, Tamil recognized well but with a minor word-split
error, and Arabic recognizing its text correctly but dropping the
numeric total line entirely (empty string at 0.0 confidence) -- see
`docs/adr/0002-ocr-backend-selection.md`'s "Update" section for the full
honest breakdown. `PaddleOCREngine.recognize()` raises
`UnsupportedBackendError` cleanly (not a crash) when the sidecar isn't
configured, and `get_default_engine()` falls back to Tesseract
automatically in that case, so a checkout with no sidecar set up is
unaffected. **The "109 languages" goal still is not fully backed**: only
English/Tamil/Arabic have been smoke-tested so far, Tamil/Arabic quality
is imperfect, and this remains flagged as follow-up work (broader
language benchmarking, plus designing the real multi-request sidecar
transport -- current wiring is a one-process-per-call stopgap).

What *is* validated end-to-end: Tesseract recognizing real rendered text
(not placeholder black bars) in three scripts -- Latin (English), Tamil,
and Arabic (RTL, correctly ordered) -- via new fixtures added to
`python/tests/fixtures/generate.py` using system fonts (Arial, Tamil MN,
SF Arabic) and real end-to-end smoke tests in
`python/tests/test_tesseract_engine.py`. Tamil/Arabic language data
(`tam.traineddata`/`ara.traineddata`, from `tesseract-ocr/tessdata_fast`,
Apache-2.0) is not bundled in the repo or installed system-wide by
default -- those two tests skip cleanly (not fail) when the data isn't
present via `RECEIPTLINGUA_CACHE_DIR`'s `tessdata/` subdir or the system
Tesseract's own tessdata directory, consistent with "never fetch missing
models automatically." Real end-to-end PaddleOCR smoke tests were added
the same way in `python/tests/test_paddleocr_engine.py`, skipping cleanly
when `RECEIPTLINGUA_PADDLE_PYTHON` isn't set. 111 of the Python test
suite's tests pass on a fresh checkout (7 skip: Tamil/Arabic Tesseract
language data plus the 5 PaddleOCR sidecar tests, all set up and
verified passing locally in this session).

Not done, out of scope for this milestone per the task brief: structured
field extraction (101-120), the Surya benchmark-only adapter (deprioritized
in favor of getting one real backend fully working end to end -- tracked
as future work), MPS/CUDA accelerator probing (Tesseract is CPU-only, and
the PaddleOCR sidecar smoke test used CPU inference only -- GPU probing
for the sidecar is future work), and designing the real multi-request
sidecar transport (current PaddleOCR wiring is a one-process-per-call
subprocess stopgap, not the final protocol).

81-100 (language/script detection) done as of 2026-09-27. Unicode script
segmentation uses the `regex` package's `\p{Script=...}` property
matching (verified installable, MIT-permissive-adjacent PSF-style
license, pure add-on to stdlib `re`) rather than a hand-vendored
script-ranges table, since stdlib `unicodedata` has no direct script
query. Language ID uses `py3langid` (MIT, maintained fork of
`langid.py`): chosen over fastText's `lid.176` because its model is
bundled in the pip package itself with no separate download step, which
this project's offline-first requirement needs. `py3langid`'s bundled
model covers 142 language labels.

The `model_supported`/`receipt_verified` matrix
(`python/src/receiptlingua/langid/data/language_matrix.json`, rendered as
`LANGUAGES.md`) currently has **87 of 94 tracked languages marked
`model_supported = true`**, including all 32 mandatory high-priority
languages. `model_supported` required *both* a py3langid label *and* a
documented Tesseract `tessdata_fast` language pack -- not just being on
the mandatory wishlist. The 7 `false` entries are honest gaps: languages
with a Tesseract pack but no py3langid label (Tibetan, Dhivehi,
Tigrinya, Tongan, Cherokee, Inuktitut) or a py3langid label but no
Tesseract pack (a Kurdish variant). Every single entry has
`receipt_verified = false`, correctly, since no receipt benchmark exists
yet (milestone 171-185).

This is short of the aspirational ~109-language target, but that gap is
**not a hard ceiling**: it reflects that only Tesseract's `eng` langpack
is actually installed in this checkout (the other 31 mandatory languages'
`.traineddata` files are documented as available upstream but not
downloaded here, same situation as the `tam`/`ara` packs fetched by hand
for milestone 56-80's smoke tests). Installing more packs via `brew
install tesseract-lang` or manual `tessdata_fast` downloads is pure
coverage-expansion, not blocked on any code written in this milestone.
Chinese Simplified/Traditional are both tracked in the matrix as
distinct entries (`zh-Hans`/`zh-Hant`, both `model_supported = true` via
Tesseract's separate `chi_sim`/`chi_tra` packs) but share py3langid's one
generic `zh` label -- documented explicitly in that entry's notes, since
py3langid alone cannot distinguish the two scripts/variants.

101-120 (structured receipt extraction) done as of 2026-09-27, in ~13
commits rather than the ~20 implied by the range (two of the planned
commits were absorbed as bugfixes into the feature commit that exposed
them -- see the amount-regex and payment-keyword fixes below -- rather
than landing as separate no-op-then-fix pairs).

Implemented under `python/src/receiptlingua/extract/`, deliberately
**rule-based, not ML-based**, for v0 -- a reasonable, honestly-scoped
choice for this milestone rather than an accuracy claim:

- `reading_order.py`: reconstructs top-to-bottom / RTL-aware reading
  order from bbox geometry (y-overlap row clustering, x-ordering within
  a row, reversed for rows whose script is RTL). Geometry-only: it does
  not detect true multi-column layouts, so a two-column receipt is
  currently ordered as one wide row -- a known limitation.
- `currency.py`: symbol + ISO 4217 code detection. Handles the
  genuinely-ambiguous cases (`¥` shared by JPY/CNY, `Rs` shared by
  several rupee currencies) by reporting an `uncertain` candidate set
  instead of guessing.
- `amounts.py`: locale-defensive number parsing (US vs. European
  separator conventions); a single separator with exactly 3 trailing
  digits (`"1,234"`/`"1.234"`) is treated as genuinely ambiguous and
  reported as such rather than resolved by guessing.
- `amount_fields.py`, `dates.py`, `merchant.py`, `receipt_number.py`,
  `payment_method.py`, `line_items.py`: keyword/pattern/heuristic
  extraction for the remaining `fields` entries, each producing a
  `ScalarField`/`LineItem` with `status` and `evidence` mirroring
  `response.schema.json`'s `scalar_field`/`line_item` defs exactly
  (`types.py`). `total` is computed and marked `inferred_field` (with
  evidence pointing at the subtotal/tax/discount lines it derives from,
  never a nonexistent total line) when the total line itself is
  missing but subtotal+tax are both present.
- `extractor.py`: `extract_fields(text_lines, rtl_flags)` orchestrates
  all of the above and remaps every field's evidence back to the
  original (pre-reading-order-reconstruction) `text_lines` indices.

**Known, deliberately-flagged weaknesses for the 171-185 benchmark
milestone**, so this is not oversold as more robust than it is:

1. **Line-item table extraction** is the weakest structural piece: it
   treats each physical line independently with no real column-x
   alignment across multiple lines, so it only works reliably on
   simple single-column layouts where one item = one line. Multi-line
   item descriptions, wrapped text, and complex multi-currency tables
   are not handled.
2. **Merchant-name extraction** is a first-few-non-noise-lines
   heuristic and is *always* returned as `status: "uncertain"`
   (never `"ok"`), by design -- it is the least reliable field here.
3. **Multilingual keyword coverage is intentionally thin**: only
   English plus a small set of high-confidence Arabic terms
   (total/tax/discount) are included in `keywords.py`. Tamil, Urdu, and
   most of the other 87 `model_supported` languages have NO keyword
   coverage here -- their standard receipt vocabulary was not sourced
   with enough confidence for this pass, so per the project's
   no-hallucination constraint those languages fall back to
   number-proximity heuristics only rather than shipping a guessed
   translation. This should be closed with native-speaker review before
   real accuracy claims are made.

Two bugs were caught by the hand-constructed tests during this
milestone (both fixed, both worth remembering): the amount-token regex
originally allowed whitespace inside a match, silently merging adjacent
numbers on a line (`"2 1.50 3.00"` parsed as one bogus token) and broke
line-item parsing entirely; and the naive `"total"` keyword match
matched inside `"subtotal"`, causing a subtotal row to be misread as the
grand total. Both are exactly the kind of failure hand-constructed
input-based unit testing (as opposed to only real-image benchmarking)
is well-suited to catch early.

121-140 (Python packaging/CLI) done as of 2026-09-27, in 5 commits. This
is the first milestone where every previous milestone's module is
actually called end-to-end from one real entry point, and integration
issues were genuinely found and fixed while doing it (not hypothetical):

- `python/src/receiptlingua/api.py` (`ReceiptOCR.scan()`): calls
  `pipeline.preprocess.orchestrator.preprocess_array`, then
  `engines.registry.get_default_engine()`/`get_engine(name)`, then
  `langid.tagging.tag_document`, then `extract.extractor.extract_fields`,
  assembling output that validates against
  `protocol/schema/response.schema.json` via `jsonschema` (checked for
  real, not assumed). Accepts a file path, raw `bytes`, `PIL.Image`, or
  `numpy.ndarray`. Errors raise `ReceiptOCRError`, reusing
  `engines/errors.py`'s `EngineError.code` vocabulary rather than
  inventing a second error taxonomy, and additionally cover
  `INVALID_IMAGE`/`UNSUPPORTED_FORMAT` (from `pipeline.preprocess.loading`)
  and `INVALID_CONFIGURATION` (bad `mode=`/unsupported input type), which
  the engine layer alone had no reason to raise.
- `python/src/receiptlingua/cli.py`: `argparse`-based (no new dependency
  -- `click` was never actually a dependency anywhere in this tree, and
  the command surface here does not need more than stdlib offers).
  Implements `scan`, `languages`, `models`, `doctor`, `cache info`, and an
  honest `benchmark` stub that says "not yet implemented, see milestone
  171-185" instead of faking a result. `doctor` never prints the *value*
  of `RECEIPTLINGUA_PADDLE_PYTHON`, only whether it is set and whether
  that interpreter actually imports `paddle`/`paddleocr`.
- `python/pyproject.toml`: added the `receiptlingua` console-script entry
  point, `package-data` for `langid/data/language_matrix.json`, an SPDX
  `license` expression, dev-status classifiers, and a `0.1.0.dev0`
  pre-release version.

**Real integration bugs found and fixed while wiring this up** (exactly
the kind the task brief warned to expect from modules built in isolated
sessions):

1. `language_matrix.json` was not included in the built wheel/sdist --
   `[tool.setuptools.packages.find]` finds Python packages but not data
   files, so `receiptlingua languages` worked in this repo's editable
   install (by `src/` sys.path accident) but broke with a bare
   `FileNotFoundError` after a genuine `pip install` from a built wheel.
   Verified by actually building a wheel (`python -m build`) and
   installing it into a throwaway venv outside the repo -- caught this
   exact failure that way, not by inspection. Fixed with
   `[tool.setuptools.package-data]`.
2. `readme = "../README.md"` in `[project]` (pointing at the repo-root
   README, since `python/` has no README of its own) fails a real build:
   setuptools refuses to read a file outside the project root
   (`python/`). Also only caught by actually running `python -m build`
   in a clean venv, not by reading the config. Removed rather than
   duplicating the README into `python/` for now, since the top-level
   README already documents the exact `from receiptlingua import
   ReceiptOCR` usage this milestone implements.
3. Tesseract's `recognize()` needs an explicit `languages=` tuple to ever
   load a non-`eng` language pack -- `ReceiptOCR` did not thread this
   through in its first draft, so passing `languages=("tam",)` silently
   had no effect (always recognized as `eng`) until `_run_ocr` was fixed
   to call `engine.recognize(pixels, languages=self.languages)`. This
   pipeline still has **no automatic language-ID pre-pass** to pick
   languages on its own (documented in `api.py`'s docstring) -- a caller
   must currently name the language(s) explicitly for anything but
   English to actually engage the right OCR language data. Flagged here
   as a real, known gap, not silently left for someone to discover later.
4. `langid.tagging.tag_document`'s document-level `languages` list sums
   every line's full confidence-weighted ranking (not just each line's
   top guess), which for short receipt text produces a very long,
   mostly-near-zero-confidence tail (in one English fixture test, ~140
   entries down to confidence 0.001). This is correct per that module's
   own design intent (supporting genuinely mixed-language documents) and
   was left as-is rather than changed, since it is existing, tested
   behavior from milestone 81-100, not a defect introduced here -- but
   the CLI's human-readable `scan` output was given a `>= 0.05`
   confidence filter (capped at 5 entries) so it is actually usable
   day-to-day; `--json` still returns the full, unfiltered list from the
   API for anyone who wants it.

**Verified for real, not just "it runs from the repo root"**: built a
wheel with `python -m build`, installed it with `pip install
<wheel>.whl` into a throwaway venv created outside this repo, then ran
`receiptlingua doctor`, `receiptlingua languages`, `receiptlingua models`,
`receiptlingua cache info`, `receiptlingua benchmark`, and
`receiptlingua scan <fixture> --json` from that venv's `cwd=/tmp`, with
the JSON output re-validated against `response.schema.json`. `import
receiptlingua`, `receiptlingua.ReceiptOCR`, and the console script all
work from a genuine fresh install, not by sys.path accident.

Full Python test suite: 220 pre-existing tests still pass, plus 23 new
integration tests added here (`test_api_integration.py`,
`test_cli.py`) -- 243 passed, 9 skipped (Tamil/Arabic Tesseract language
data and the 5 PaddleOCR sidecar tests, same honest skip conditions as
milestone 56-80, unaffected by this milestone's changes). `ruff check .`
passes clean on all new/changed files.

**Known follow-up, not papered over**: no automatic language
identification pre-pass exists yet to pick OCR languages on its own
(item 3 above) -- multilingual `scan()` calls currently require the
caller to pass `languages=(...)` explicitly. This is the natural next
integration point once a language-ID-on-a-fast-pass design is worked
out (a real chicken-and-egg problem: you need *some* OCR text to run
language ID on before you know which language's OCR to run). Also
unchanged from prior milestones and still open: the PaddleOCR sidecar
remains a one-process-per-call stopgap (not the final transport), and
only English/Tamil/Arabic have any real language-pack/benchmark
verification at all.

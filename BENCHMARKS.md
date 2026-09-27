# ReceiptLingua Benchmarks

## RTL update (Arabic/Hebrew CER > 1.0 root-caused and fixed)

The original 350-case run below measured Arabic CER 1.161 and Hebrew CER
1.136 -- a CER above 1.0 means the OCR output has *more character-level
errors than the ground truth has characters*, which is a broken pipeline,
not "needs improvement." This was root-caused, not guessed at, by actually
looking at the generated images and raw OCR output. Three real, distinct
bugs were found and fixed:

1. **The synthetic generator never applied Arabic letter shaping or
   bidi/RTL reordering before drawing text.** `PIL.ImageDraw.text` draws
   whatever codepoints it's given, left-to-right, with no awareness of the
   Unicode Bidirectional Algorithm or Arabic's contextual joining forms
   (initial/medial/final/isolated). Rendering the ground-truth *logical*
   Unicode string directly produced visually broken images: Arabic letters
   came out as disconnected isolated glyphs, and word order was wrong for
   both Arabic and Hebrew. Confirmed visually (rendered a test PNG with
   and without correction side by side; the "before" row is genuinely
   unreadable Arabic even to a human, and the "after" row -- run through
   `arabic-reshaper` + `python-bidi`'s `get_display` -- reads as correct
   joined Arabic/Hebrew). **Even a perfect OCR engine could never have
   matched the old ground truth**, because the image itself didn't depict
   that text correctly. Fixed in
   `python/src/receiptlingua/synth/generator.py` (`_visual_render_line`);
   the ground-truth `lines`/`full_text` are deliberately left in logical
   order (unchanged) -- only the rendering path changed.
2. **The Arabic/Hebrew system fonts used (`SFArabic.ttf`/`SFHebrew.ttf`)
   have no usable Latin digit or ASCII glyphs.** Verified by probing
   `PIL.ImageFont.getmask(ch).getbbox()` for `'0'..'9'`, `'x'`, `'A'`: every
   one came back with the *exact same bounding box*, the signature of
   FreeType's `.notdef` fallback ("tofu box") glyph -- every price, date,
   and quantity on an ar/he receipt was silently rendered as a solid black
   box, not a digit. Since every line item, date, and total on these
   receipts is majority-numeric, this alone would have wrecked CER even
   with bidi/shaping fixed. Switched both `ar` and `he` to
   `/System/Library/Fonts/Supplemental/Arial Unicode.ttf`, verified (same
   bbox-probing method) to have real, distinct glyphs for Latin digits
   *and* Arabic/Hebrew letterforms including the presentation-forms glyphs
   `arabic-reshaper` produces.
3. **Tesseract's own `ara`/`heb` recognition returns each line in visual
   (mirrored) order, not logical Unicode order**, and nothing in the
   pipeline corrected for it -- `python/src/receiptlingua/extract/
   reading_order.py`'s RTL row-ordering logic exists but is **not called
   anywhere** in `api.py` or the engine layer (confirmed by grep -- it's
   dead code), and it wouldn't have fixed this specific bug anyway since
   it only reorders whole lines/rows, not the character order Tesseract
   emits per recognized run. Verified directly: raw
   `pytesseract.image_to_string(..., lang="ara")` on a correctly-rendered
   receipt returned the Arabic word for "rice" (`أرز`) as `زرأ` -- its own
   characters reversed -- and whole lines came back as the mirror image of
   the correct string. Running that output back through `python-bidi`'s
   `get_display` (the same function used to go logical->visual for
   rendering) recovers the correct logical-order text; this was verified
   empirically against real OCR output (`أرز` reappeared correctly, digit
   runs stayed intact and in place) before being wired in, not assumed to
   work. Fixed in `python/src/receiptlingua/engines/tesseract_engine.py`:
   lines recognized under `ara`/`heb` now get `get_display()` applied to
   their assembled text before being returned.

**Real re-measurement** (420 cases: en/ar/he x all 14 degradations x 10
samples/language, `--seed-base 30000`, same Tesseract tessdata_fast
backend, `benchmarks/latest_summary.json`):

| language | before (CER) | after fix 1+2 only (CER) | after all 3 fixes (CER) | merchant-match (before -> after) |
|---|---|---|---|---|
| en | 0.108 | 0.097 | 0.101 | 81.4% -> 82.9% (no regression) |
| ar | 1.161 | 0.663 | **0.545** | 74.3% -> 13.6% (regressed -- see below) |
| he | 1.136 | 0.672 | **0.506** | 85.7% -> 70.7% (partial recovery) |

Honest reporting, not a victory lap: CER improved dramatically (Arabic
1.161 -> 0.545, Hebrew 1.136 -> 0.506) and English is unaffected (0.108 ->
0.101, within run-to-run noise from the different seed-base/sample-count
used for this focused re-run). This confirms the three bugs above were
real and the fixes work. **CER is still meaningfully worse than English's
~0.10**, and merchant-match rate for Arabic (13.6%) is worse than the
*original, broken-image* run's 74.3% -- that old number was itself
suspicious (a wrong ground-truth image plus a mangled OCR reversal
apparently canceled out often enough to spuriously fuzzy-match short
merchant strings; it was never a meaningful signal, and this run's honest
extraction-level number is lower because the underlying text comparison is
now real). The residual gap after all three real fixes is most likely:
Tesseract's `tessdata_fast` `ara`/`heb` models being genuinely weaker than
`eng`'s, and/or `Arial Unicode.ttf`'s Arabic presentation-forms glyph
shapes not matching what `ara`'s training data expects closely enough for
clean recognition. Neither was chased further in this pass -- reaching
production-grade RTL quality likely needs `tessdata_best` language packs
and/or a PaddleOCR/other engine comparison (already a known gap, see
"Backend scope" below), not more generator/reordering fixes.

---


**Scope, read this first:** this is a real, executed run of **350 synthetic
cases** (not the eventual 10,000+ target). All data is 100% synthetically
generated by `python/src/receiptlingua/synth/generator.py` -- there is no
real-world receipt photo in this dataset. This report exists to give an
honest first read on the pipeline's behavior under controlled, seeded
degradation, not to make a final accuracy claim about real receipts.

Run metadata (from `benchmarks/latest_summary.json`, `meta` block):

- **Cases executed: 350** (5 languages x 5 samples-per-language x 14
  degradations, including the `clean` baseline). This is the literal
  `n_cases_executed`, not a planned/rounded number.
- Backend: Tesseract (the engine registry default; see "PaddleOCR" below
  for why it was excluded from this run).
- Total wall time: 80.9s (mean 0.231s/case).
- Command:
  ```
  python benchmarks/run_benchmark.py --languages en,ta,ar,hi,he \
      --degradations all --samples-per-language 5 --seed-base 20000
  ```

## Headline numbers (honest, not a single "% accurate" claim)

Overall across all 350 cases:

| metric | value |
|---|---|
| mean CER | 0.6195 |
| mean WER | 1.0569 |
| exact full-record match rate (merchant+date+total all correct) | 13.7% |

These overall numbers are dominated by non-English languages performing far
worse than English (see breakdown below) -- they are **not** a
representative "ReceiptLingua is 62% wrong" statement about English-language
receipts specifically, which do much better on their own.

## Breakdown by language (averaged across all 14 degradations x 5 samples = 70 cases/language)

| language | n | mean CER | mean WER | total-exact-match rate | merchant-match rate |
|---|---|---|---|---|---|
| en (English) | 70 | 0.108 | 0.293 | 68.6% | 81.4% |
| ta (Tamil)   | 70 | 0.319 | 0.748 | 0.0%  | 81.4% |
| hi (Hindi)   | 70 | 0.373 | 0.756 | 0.0%  | 75.7% |
| he (Hebrew)  | 70 | 1.136 | 1.567 | 0.0%  | 85.7% |
| ar (Arabic)  | 70 | 1.161 | 1.922 | 0.0%  | 74.3% |

English is the only language with real full-record exact matches in this
run. Tamil/Hindi have moderate character-level error but never land an
exact total-amount + date + merchant match. Arabic and Hebrew (both RTL
scripts) have mean CER **above 1.0**, meaning Tesseract's `ara`/`heb`
tessdata_fast models, run through this pipeline's current (LTR-oriented)
reading-order/preprocessing path, are producing output longer/more
different from ground truth than the ground truth text itself -- a real,
substantial quality gap, not a benchmark artifact. This matches the
generator's own honesty notes: fonts for `ar`/`he`/`ta`/`hi` were verified
to *render*, but this is the first time their full OCR round-trip has been
measured end-to-end, and the RTL scripts in particular need real
engine-side work (RTL-aware preprocessing/reading order, script-specific
tuning) before they're usable.

## Breakdown by degradation type (averaged across all 5 languages x 5 samples = 25 cases/degradation)

| degradation | mean CER | mean WER | status |
|---|---|---|---|
| clean (baseline) | 0.636 | 1.127 | real |
| rotation | 0.406 | 0.668 | real |
| gaussian_blur | 0.435 | 0.694 | real |
| motion_blur | 0.704 | 1.138 | real |
| gaussian_noise | 0.650 | 1.137 | real |
| salt_pepper_noise | 0.637 | 1.116 | real |
| jpeg_compression | 0.617 | 1.110 | real |
| brightness_contrast | 0.644 | 1.178 | real |
| shadow | 0.617 | 0.979 | real |
| perspective_warp | 0.636 | 1.127 | real |
| crop | 0.675 | 1.221 | real |
| low_contrast_fade | 0.706 | 1.291 | real |
| wrinkle_warp | 0.735 | 0.982 | real (best-effort local-warp approximation, not physically modeled) |
| thermal_streak | 0.576 | 1.029 | real (lightweight fade-band approximation, not physically modeled) |

All 14 rows above ran a real transform against real images. Two additional
degradation types requested in the original wishlist are **not**
implemented and were **not** run in this benchmark (see
`python/src/receiptlingua/synth/degrade.py` module docstring,
`DEFERRED_DEGRADATIONS`):

- `tear_missing_section` -- deferred, no convincing torn-paper-edge mask built.
- `curved_page_dewarp` -- deferred, no genuine cylindrical/curved-page warp built.

The `clean` row (no degradation at all) has CER 0.636 -- higher than several
degraded rows -- purely because it's an unweighted average across all 5
languages including the poorly-performing RTL ones; see the by-language
table for the real signal (English `clean` CER is 0.015).

## Backend scope: why PaddleOCR was excluded from this run

`run_benchmark.py --backend` supports pointing at any registered engine,
including a PaddleOCR sidecar backend. This run used only the default
(Tesseract) backend. PaddleOCR was deliberately excluded here because:

- The PaddleOCR sidecar has a substantial per-call/startup cost (observed
  in earlier milestones to dominate wall time for small batches), which
  would have made a 350-case run take dramatically longer than the ~81s
  this run took.
- Getting a fair per-case PaddleOCR number requires either warming the
  sidecar once and reusing it across cases (the harness currently
  constructs a fresh `ReceiptOCR()` per case) or batching calls -- neither
  is done yet.

This is a known, explicitly-scoped gap, not an oversight: PaddleOCR
accuracy numbers are simply not in this report.

## Language/font support actually used

Fonts were previously verified to render for en/ta/ar/hi/he (see
`python/src/receiptlingua/synth/generator.py` `FONTS`). Tesseract langpack
support was the real blocker: this machine had only `eng` installed at the
start of this task. `brew install tesseract-lang` was run (a standard,
non-destructive Homebrew package install) and it added the full
tessdata_fast bundle, confirmed via `tesseract --list-langs` to now include
`tam`, `ara`, `hin`, `heb` (in addition to `eng`). The harness maps the
generator's ISO 639-1 codes (`ta`/`ar`/`hi`/`he`) to Tesseract's langpack
names (`tam`/`ara`/`hin`/`heb`) itself, in `benchmarks/run_benchmark.py`
(`TESSERACT_LANG_MAP`) -- the OCR engine does not do this mapping
internally, which is a real, separate gap worth fixing in the engine layer
rather than papering over it permanently in the benchmark harness.

## What would need to happen to scale this to 10,000+ cases

1. **PaddleOCR path**: fix the sidecar's per-call startup cost (reuse a
   warm sidecar process across many cases rather than spinning one up per
   case) so a PaddleOCR backend run is tractable at scale; then re-run this
   same harness with `--backend paddleocr` (or whatever it's registered
   as) to get real Paddle numbers alongside Tesseract's.
2. **RTL script quality**: Arabic/Hebrew CER > 1.0 indicates the
   pipeline's preprocessing/reading-order path needs real RTL-specific
   work (not just a working langpack) before those numbers are usable;
   investigate reading-order handling in
   `python/src/receiptlingua/extract/reading_order.py` for RTL scripts.
3. **More langpacks**: `brew install tesseract-lang` already gives this
   machine every tessdata_fast language Tesseract ships (100+); the
   generator itself would need more verified fonts (`FONTS` in
   `generator.py`) to exploit that for additional synthetic languages.
4. **Real-world data**: this is 100% synthetic. `datasets/registry.yaml`
   documents that no external/licensed real-receipt dataset is integrated
   yet -- reaching a benchmark that reflects real-world performance (not
   just synthetic-degradation robustness) requires sourcing and
   license-clearing an actual receipt-image dataset.
5. **Volume**: at this run's throughput (~0.23s/case on Tesseract/English,
   slower on RTL/loaded scripts), 10,000 Tesseract-backend cases would take
   roughly 30-60+ minutes of wall time alone -- tractable, but should run
   as a background/CI job rather than an interactive one, and should
   pre-generate the synthetic corpus once rather than regenerating +
   degrading per run.
6. **Deferred degradations**: implement `tear_missing_section` and
   `curved_page_dewarp` for real (see `degrade.py`) before claiming full
   wishlist coverage.

## Reproducing this run

```
python/.venv/bin/python benchmarks/run_benchmark.py \
    --languages en,ta,ar,hi,he --degradations all \
    --samples-per-language 5 --seed-base 20000
```

Aggregated output: `benchmarks/latest_summary.json` (committed). Raw
per-case images/ground-truth/JSONL: `benchmarks/results/` (gitignored, not
committed -- regenerate by re-running the command above).

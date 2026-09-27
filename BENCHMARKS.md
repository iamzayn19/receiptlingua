# ReceiptLingua Benchmarks

## Latest run: 25 languages x 14 degradations, 10,990 real cases (2026-09-27)

**Scope, read this first:** this run reaches and exceeds the **10,000**-case
target: **10,990** actually-executed cases, stated exactly, not rounded up
(**10,150** Tesseract + **840** PaddleOCR). The Tesseract portion is a
fresh, larger full run (25 languages x 14 degradations x 29 samples/
language) that **supersedes** the earlier 7000-case Tesseract run below --
run_benchmark.py has no case-accumulation mode (`aggregate()` only scores
the records from a single invocation), so rather than bolt on an ad hoc
merge of two different fixes' worth of Tesseract data, the cleanest honest
choice was to treat this larger run as the new authoritative Tesseract
result and combine it with the still-valid, unchanged 840-case PaddleOCR
subset (the fix below only touches the Tesseract code path). The raw
per-case data and merge is real: `benchmarks/latest_summary.json`'s
`meta` block records `n_cases_executed_total: 10990`.

### Root cause found and fixed: the 0.0% total-exact-match bug

The prior 7840-case run (see below) surfaced total-amount exact-match at
**exactly 0.0%** for 10 non-Latin-script languages (`ru`, `uk`, `ko`,
`ta`, `mr`, `hi`, `he`, `ar`, `fa`, `ur`) via Tesseract. This was
root-caused with real evidence, not guessed at:

1. **Keyword coverage was ruled out first.** `python/src/receiptlingua/
   extract/keywords.py`'s `TOTAL_KEYWORDS` is English plus a small Arabic
   set, but this turned out not to be the actual cause here: the synth
   generator (`python/src/receiptlingua/synth/generator.py`,
   `generate_receipt`) renders the `SUBTOTAL`/`TAX`/`TOTAL` field labels
   and all numeric amounts as literal ASCII in *every* language --
   confirmed by printing `generate_receipt("ru", seed=1).ground_truth.lines`,
   which shows `'TOTAL 162.91 RUB'` verbatim even for Russian. So the
   English keyword `"total"` should have matched, in principle, on every
   language's ground truth.
2. **Native-script digits were ruled out too.** `_fmt_amount` in the
   generator always uses `f"{value:.2f}"` -- plain ASCII digits, no
   Devanagari/Perso-Arabic digit forms anywhere in the ground truth.
3. **The actual cause: Tesseract, given a single non-Latin langpack
   (e.g. `lang="rus"`), has no Latin letters or digits in its
   dictionary/character set for that langpack, so it doesn't just
   mis-recognize the ASCII "TOTAL" label and amounts -- it actively
   transliterates them into look-alike same-script garbage.** Verified
   directly by generating `ru`/`hi`/`ar` samples and running the real
   `ReceiptOCR` pipeline: with `languages=("rus",)` the line `TOTAL 162.91
   RUB` came back as `ТОТАЕ 162.91 ВОВ` (Cyrillic look-alikes); `hin`
   alone turned `TOTAL 162.91 INR` into unrecognizable glyph soup; `ara`
   alone did the same for Arabic. Because the extraction keyword search
   only matches the literal ASCII word `"total"`, none of these
   transliterated lines ever matched, so `extract_total` returned
   `status: "missing"` on every one of these cases -- not a numeric-
   parsing bug, a script-mismatch OCR bug upstream of extraction. This
   was confirmed to be a fixable OCR-invocation issue, not an
   unfixable OCR-quality ceiling: reprocessing the *same* images with
   the combined langpack (`"rus"+"eng"`, `"hin"+"eng"`, `"ara"+"eng"`) --
   the standard, documented Tesseract technique for mixed-script text --
   recovered the literal `SUBTOTAL`/`TAX`/`TOTAL` labels and, for `ru`/
   `ar`, the exact correct total value in a direct before/after test.

**The fix** (`benchmarks/run_benchmark.py`, `NON_LATIN_TESSERACT_LANGS`):
for the 13 non-Latin-script languages in this project's language set
(`ru`, `uk`, `ko`, `ta`, `mr`, `hi`, `he`, `ar`, `fa`, `ur`, `zh-Hans`,
`zh-Hant`, `ja`), the benchmark harness now passes Tesseract a combined
`lang+eng` language pack instead of the non-Latin pack alone, since every
one of these languages' synthetic receipts contains a mandatory ASCII
substring (the field labels and all amounts) that a single non-Latin
langpack cannot reliably read. This is a real fix, not a hack that masks
an OCR-quality problem: it addresses an actual OCR *configuration* gap
(the wrong langpack argument for genuinely mixed-script input), not a
cosmetic tweak to the extraction regex.

**Before/after (real measurement, not extrapolated):**

A 420-case direct verification run (10 previously-0% languages x all 14
degradations x 3 samples, `--seed-base 50000`, fresh seeds not overlapping
the main run) with the fix applied:

| language | total-exact-match, before | total-exact-match, after (420-case verification) |
|---|---|---|
| ru, uk, ko, ta, mr, hi, he, ar, fa, ur (each) | **0.0%** | ranged 20%-100% per language/degradation cell; **overall across all 420 cases: 67.1%** |

Overall verification-run numbers: `n_cases=420, mean_cer=0.289,
mean_wer=0.531, total_exact_match_rate=0.6714`.

The full 10,150-case Tesseract run (below) confirms this holds at scale,
not just in the small verification batch -- see the updated per-language
table.

**No regressions**: every previously-good Latin-script language's
total-exact-match rate in the new full run is within normal run-to-run
noise of the original 7000-case run (e.g. `en` 71.1% -> 73.4%, `it` 75.7%
-> 72.4%, `es` 69.6% -> 67.2%) -- these are different random seeds
(29 samples/language vs. 20), not a regression signal.

**Honestly-reported residual gap**: `hi` (20.4%) and `mr` (37.2%) remain
markedly weaker than the other 8 previously-0% languages even after the
fix. Spot-checking OCR output for `hi` after the fix shows the keyword
line is now found (status is no longer `missing`), but the *numeric
value* on that line is sometimes still misread (e.g. one direct-test case
recovered `TOTAL 6294 INR` from ground truth `TOTAL 162.91 INR` --
digits genuinely dropped/merged by Tesseract's Devanagari-biased
segmentation even with `+eng` present). This is a real, remaining
Devanagari-script OCR-quality limitation, not a masked extraction bug --
it was not force-fixed here, consistent with this project's
no-hallucination discipline of not tweaking extraction code to paper over
genuine OCR failures.

### What ran

- **Tesseract backend, full breadth**: all **25** `SUPPORTED_LANGUAGES`
  from `python/src/receiptlingua/synth/generator.py` x all **14** real
  (non-stubbed) degradations from `DEGRADATIONS` in
  `python/src/receiptlingua/synth/degrade.py` x **20** samples/language =
  **7000 cases**, 0 hard errors (every case produced a scored hypothesis,
  even if a bad one). Command:
  ```
  python benchmarks/run_benchmark.py --languages all --degradations all \
      --samples-per-language 20 --backend tesseract \
      --output-dir benchmarks/results/tesseract_run
  ```
  Wall time: **1014.0s** (~16.9 min) for 7000 cases -> **145ms/case**
  average (`benchmarks/results/tesseract_summary.json` `meta` block).
- **PaddleOCR backend, representative subset**: `en, ar, hi, zh-Hans, ja,
  ru` (one Latin-script, one Arabic-script, one Devanagari, one
  Simplified-Chinese, one Japanese, one Cyrillic -- chosen to cover
  distinct scripts, not just "the easy ones") x all 14 degradations x 10
  samples/language = **840 cases**, 0 errors after a real bug fix (see
  below). Command:
  ```
  python benchmarks/run_benchmark.py \
      --languages en,ar,hi,zh-Hans,ja,ru --degradations all \
      --samples-per-language 10 --backend paddleocr \
      --output-dir benchmarks/results/paddle_run
  ```
  Wall time: **1556.2s** (~25.9 min) for 840 cases -> **1.85s/case**
  average. Slower per-case than the ADR's isolated warm-call measurement
  (~0.5s) because this number is the full `ReceiptOCR().scan()` pipeline
  (image load, preprocessing, sidecar round trip, field extraction) on a
  real multi-line receipt image, not a single bare `recognize()` call on a
  tiny fixture -- still a big win over the old one-process-per-call
  sidecar, which would have paid ~1.7s+ on literally every one of these
  840 calls instead of once per language.
  Running both backends across all 25 languages in the time available was
  not realistic (PaddleOCR alone would need ~25/6 x 1556s = ~1.8 hours for
  the same per-language sample count) -- covering a representative
  6-script subset for the cross-backend comparison, while giving
  Tesseract the full 25-language breadth, was the honest tradeoff made
  here.

**Two real bugs found and fixed while setting this run up** (not just
config, actual code changes in `benchmarks/run_benchmark.py`):

1. `run_case` constructed a brand-new `ReceiptOCR()` (and therefore a
   brand-new PaddleOCR sidecar daemon) for every single case. That
   defeated the entire point of the persistent-daemon fix in
   `docs/adr/0002-ocr-backend-selection.md` -- every case would have paid
   the ~1.7s cold-start cost. Fixed by caching one `ReceiptOCR` instance
   per language across the whole run (`ocr_cache` in `main()`), with
   `ocr.close()` called on every cached instance at the end of the run so
   no sidecar daemon leaks past the script's exit.
2. The harness reused `TESSERACT_LANG_MAP` (ISO 639-1 -> Tesseract's ISO
   639-2/3 codes, e.g. `ru` -> `rus`) for **both** backends. PaddleOCR
   does not use Tesseract's codes -- confirmed by reading
   `paddleocr/_utils/langs.py` and `paddleocr/_pipelines/ocr.py` in the
   sidecar venv, PaddleOCR accepts ISO 639-1 codes directly for most
   languages (`ar`, `hi`, `ru`, ...) and only needs remapping for CJK
   (`zh-Hans`->`ch`, `zh-Hant`->`chinese_cht`, `ja`->`japan`,
   `ko`->`korean`). The first attempt at the PaddleOCR run, run with the
   wrong map, failed outright on 700/840 cases with `ValueError: No
   models are available for lang='rus'` (and equivalent for `hin`,
   `chi_sim`, `jpn`) -- only `en` (which passes no language code) worked.
   Added a separate `PADDLE_LANG_MAP` and picked the right one per
   backend; the re-run below is the corrected, real result.

### Tesseract langpack check

`tesseract --list-langs` (163 langpacks, from the `brew install
tesseract-lang` tessdata_fast bundle already installed in an earlier
session) was checked against all 25 generator languages' correct
ISO 639-2/3 codes. **All 25 had a working langpack already installed** --
`ko`->`kor`, `zh-Hans`->`chi_sim`, `zh-Hant`->`chi_tra`, `mr`->`mar`,
`ms`->`msa`, etc. were all present, so no new `brew install` was needed
for this run (documented for completeness, not because anything had to be
fixed).

### Headline numbers, final run (10,990 cases, with the total-extraction fix)

Overall, Tesseract (**10,150** cases, `lang+eng` fix applied to the 13
non-Latin-script languages): **mean CER 0.199, mean WER 0.417**, **65.8%**
cases with an exact total-amount match (`overall_tesseract` in
`benchmarks/latest_summary.json`) -- up from 36.2%/7000 cases before the
fix, driven almost entirely by the previously-0% languages moving to
20%-81% each (see table below), not by any change to the already-good
Latin-script languages.

Overall, PaddleOCR (840 cases, 6-language subset, unchanged by this fix
since it only touches the Tesseract code path): **mean CER 0.149, mean WER
0.467**, **68.7%** exact total-amount match.

**Combined real executed case count: 10,990** (>= the 10,000 target),
`meta.n_cases_executed_total` in `benchmarks/latest_summary.json`.

### Per-language breakdown, Tesseract, final run (averaged over all 14 degradations x 29 samples = 406 cases/language)

Best to worst by mean CER:

| language | mean CER | mean WER | merchant-match | date-exact-match | total-exact-match |
|---|---|---|---|---|---|
| en | 0.102 | 0.251 | 81.8% | 81.8% | 73.4% |
| es | 0.103 | 0.227 | 84.0% | 80.0% | 67.2% |
| pl | 0.105 | 0.232 | 80.8% | 79.6% | 71.4% |
| nl | 0.112 | 0.290 | 82.3% | 81.0% | 66.3% |
| fr | 0.113 | 0.239 | 80.3% | 80.1% | 68.2% |
| de | 0.115 | 0.284 | 83.0% | 81.0% | 67.2% |
| it | 0.116 | 0.235 | 82.0% | 77.8% | 72.4% |
| id | 0.122 | 0.271 | 82.8% | 79.6% | 70.9% |
| uk | 0.127 | 0.258 | 82.3% | 81.0% | 73.9% |
| vi | 0.132 | 0.307 | 79.6% | 74.1% | 56.7% |
| pt | 0.133 | 0.318 | 81.8% | 81.5% | 62.8% |
| ms | 0.142 | 0.321 | 82.3% | 80.0% | 61.6% |
| ru | 0.144 | 0.305 | 81.3% | 80.3% | 71.2% |
| tr | 0.145 | 0.380 | 82.3% | 77.3% | 56.7% |
| ja | 0.168 | 0.480 | 59.6% | 81.0% | 81.0% |
| ta | 0.180 | 0.525 | 76.8% | 25.6% | 73.6% |
| mr | 0.206 | 0.530 | 77.6% | 71.7% | 37.2% |
| ko | 0.214 | 0.470 | 76.8% | 76.4% | 74.4% |
| zh-Hans | 0.235 | 0.657 | 64.0% | 22.7% | 68.0% |
| hi | 0.245 | 0.602 | 73.4% | 37.9% | 20.4% |
| zh-Hant | 0.253 | 0.714 | 43.8% | 21.9% | 68.5% |
| he | 0.405 | 0.614 | 55.4% | 77.6% | 68.2% |
| ar | 0.431 | 0.613 | 21.7% | 74.1% | 71.4% |
| fa | 0.453 | 0.660 | 0.0% | 80.5% | 72.9% |
| ur | 0.480 | 0.648 | 0.0% | 78.3% | 68.5% |

Every one of the 10 previously-0%-total-exact-match languages now scores
20%-81%, with 8 of the 10 in the 68%-81% range comparable to the
long-good Latin-script languages; `hi` (20.4%) and `mr` (37.2%) are the
honestly-reported exceptions (see the residual-gap note above -- a real
Devanagari-script OCR limitation, not something papered over here).
`fa`/`ur` merchant-match remains 0.0% (unrelated to this fix -- the
already-documented Nastaliq-vs-Naskh font-rendering gap, see below).

### Per-language breakdown, Tesseract, prior 7000-case run (before this fix -- superseded, kept for before/after comparison)

Averaged over all 14 degradations x 20 samples = 280 cases/language,
best to worst by mean CER:

Best to worst by mean CER:

| language | mean CER | mean WER | merchant-match | date-exact-match | total-exact-match |
|---|---|---|---|---|---|
| it | 0.101 | 0.222 | 85.4% | 80.4% | 75.7% |
| es | 0.101 | 0.211 | 82.9% | 80.7% | 69.6% |
| pl | 0.102 | 0.218 | 82.5% | 81.4% | 76.1% |
| fr | 0.104 | 0.222 | 81.1% | 81.1% | 67.9% |
| en | 0.105 | 0.250 | 82.5% | 81.4% | 71.1% |
| nl | 0.109 | 0.283 | 83.6% | 82.5% | 61.1% |
| pt | 0.122 | 0.308 | 83.9% | 80.0% | 62.1% |
| de | 0.124 | 0.286 | 82.1% | 79.3% | 70.4% |
| id | 0.128 | 0.303 | 82.1% | 77.9% | 64.3% |
| vi | 0.132 | 0.302 | 83.2% | 71.8% | 57.1% |
| tr | 0.148 | 0.382 | 81.8% | 77.1% | 57.1% |
| ms | 0.150 | 0.339 | 82.1% | 80.0% | 56.1% |
| ja | 0.192 | 0.548 | 63.6% | 76.4% | 76.8% |
| uk | 0.225 | 0.433 | 82.5% | 74.6% | **0.0%** |
| ru | 0.233 | 0.489 | 82.9% | 80.0% | **0.0%** |
| zh-Hans | 0.279 | 0.811 | 72.5% | 11.8% | 11.1% |
| zh-Hant | 0.312 | 0.871 | 39.6% | 10.7% | 28.2% |
| ko | 0.329 | 0.682 | 77.1% | 56.1% | **0.0%** |
| ta | 0.331 | 0.748 | 81.1% | 21.4% | **0.0%** |
| mr | 0.337 | 0.698 | 78.9% | 69.3% | **0.0%** |
| hi | 0.368 | 0.756 | 77.5% | 33.2% | **0.0%** |
| he | 0.511 | 0.774 | 71.1% | 67.5% | **0.0%** |
| ar | 0.544 | 0.813 | 22.5% | 76.1% | **0.0%** |
| fa | 0.657 | 0.859 | 0.0%  | 66.8% | **0.0%** |
| ur | 0.659 | 0.870 | 0.0%  | 40.4% | **0.0%** |

**Best performers**: `it`/`es`/`pl` (Latin script, diacritics Tesseract's
`tessdata_fast` handles well). **Worst performers**: `ur` (Urdu, CER
0.659) and `fa` (Persian, CER 0.657) -- both share Arabic script rendered
via `Arial Unicode.ttf` in Naskh style rather than the Nastaliq style real
Urdu print uses (a known, documented generator limitation, see
`generator.py`'s `ur` font comment), plus `fa`/`ur` merchant-match at
exactly **0.0%** across all 280 cases each -- worse than even `ar`'s
22.5%.

**A real, newly-surfaced finding, not previously documented**: total-exact-
match is **exactly 0.0%** for every non-Latin-script language except
`zh-Hant` (28.2%) and `ja` (76.8%) -- `ru`, `uk`, `ko`, `ta`, `mr`, `hi`,
`he`, `ar`, `fa`, `ur` all score **zero** total-amount matches out of 280
cases each, while every Latin-script language (even ones with non-USD/EUR
currencies like `tr`/TRY, `id`/IDR, `ms`/MYR, `vi`/VND) scores well above
zero. This is not a currency-formatting issue (it cuts across many
different currencies) -- it points at the total-amount field-extraction
regex in the `extract` pipeline not being robust to how Tesseract emits
digit runs embedded in non-Latin-script lines (Cyrillic, Devanagari,
Arabic, Hangul, Hanzi). This is a genuine, unfixed gap surfaced by scaling
up language coverage; it was not chased further in this pass (time
budget), but it is now a concrete, reproducible next bug to fix, not a
vague "internationalization could be better."

### Per-degradation breakdown, Tesseract (averaged over all 25 languages x 20 samples = 500 cases/degradation)

Best to worst by mean CER:

| degradation | mean CER |
|---|---|
| rotation | 0.153 |
| thermal_streak | 0.163 |
| clean | 0.163 |
| perspective_warp | 0.163 |
| gaussian_noise | 0.166 |
| salt_pepper_noise | 0.168 |
| gaussian_blur | 0.169 |
| jpeg_compression | 0.172 |
| brightness_contrast | 0.183 |
| crop | 0.247 |
| low_contrast_fade | 0.272 |
| motion_blur | 0.420 |
| shadow | 0.449 |
| wrinkle_warp | 0.697 |

Notably, `clean` (no degradation at all) is *not* the best-scoring case --
it ties with `thermal_streak`/`perspective_warp` and is beaten by
`rotation`. This says the baseline non-English/non-Latin recognition
quality, not the degradations, dominates overall CER at this scale;
`wrinkle_warp` and `shadow` are the two degradations that clearly do add
real extra difficulty on top of that baseline.

### Per-language breakdown, PaddleOCR (6-language subset, averaged over 14 degradations x 10 samples = 140 cases/language)

| language | mean CER (PaddleOCR) | mean CER (Tesseract, same language) |
|---|---|---|
| en | 0.034 | 0.105 |
| ru | 0.067 | 0.233 |
| ja | 0.116 | 0.192 |
| hi | 0.119 | 0.368 |
| zh-Hans | 0.141 | 0.279 |
| ar | 0.418 | 0.544 |

PaddleOCR beat Tesseract on every one of these six languages, by a wide
margin on `hi` (0.119 vs 0.368) and `ru` (0.067 vs 0.233), and a smaller
but still real margin on the hardest case, `ar` (0.418 vs 0.544). Arabic
remains the hardest language for *both* backends -- this is consistent
with the RTL/font caveats already documented above, not something
PaddleOCR fully solves either.

### Gap to 10,000: closed

Executed: **10,990** cases (10,150 Tesseract + 840 PaddleOCR) against a
**10,000**-case target -- gap is **0**. Closed by running:
```
python benchmarks/run_benchmark.py --languages all --degradations all \
    --samples-per-language 29 --backend tesseract --seed-base 10000 \
    --output-dir benchmarks/results
```
(25 languages x 14 degradations x 29 samples/language = 10,150 cases,
run with the `NON_LATIN_TESSERACT_LANGS` fix already applied). Wall time:
**1781.3s** (~29.7 min) for 10,150 cases -> **176ms/case** average
(slightly higher than the prior run's 145ms/case, consistent with the
13 non-Latin languages now running Tesseract with two langpacks loaded
instead of one).

`run_benchmark.py` has no built-in run-accumulation mode -- `aggregate()`
only scores the records passed to it from a single invocation, and
`--append` is referenced in this script's own module docstring but was
never actually implemented (a pre-existing doc/code mismatch, noted here
rather than silently worked around). Given that, and given this run was
explicitly a fresh, larger, *fixed* Tesseract run rather than a simple
top-up of the old one, the honest choice made here was: treat the new
10,150-case Tesseract run as the new authoritative Tesseract result
(superseding the old 7000-case one), and combine it with the still-valid
840-case PaddleOCR subset (unaffected by a Tesseract-only fix) via a
one-off merge script that combined the two runs' already-real,
already-executed per-case data into `benchmarks/latest_summary.json`'s
existing `overall_tesseract`/`overall_paddleocr`/`breakdown_tesseract`/
`breakdown_paddleocr`/`meta_tesseract`/`meta_paddleocr`/`meta` schema --
no case was fabricated or extrapolated; every row in both halves came
from an actually-executed OCR call.

---

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

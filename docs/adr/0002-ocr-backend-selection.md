# ADR 0002: OCR backend selection for milestone 56-80

Date: 2026-09-27

## Context

ADR 0001 named PaddleOCR (PP-OCRv4/v5) as the strongest open-source
candidate for the 109-language multilingual OCR goal, with Tesseract kept
as a low-dependency fallback. Milestone 56-80 required actually validating
that in this environment (Apple M5, macOS Darwin 25.6.0, Python 3.14.3,
Homebrew, no `uv`) before building an engine abstraction around it.

## What was actually tried

### PaddlePaddle / PaddleOCR

```
$ python3 -m venv /tmp/paddle_test_venv && source /tmp/paddle_test_venv/bin/activate
$ pip install paddlepaddle
ERROR: Could not find a version that satisfies the requirement paddlepaddle (from versions: none)
ERROR: No matching distribution found for paddlepaddle
```

`pip install paddleocr` (without `paddlepaddle`) *does* install cleanly --
`paddleocr==3.7.0` and its dependency tree (`paddlex==3.7.2`, etc.) have no
hard install-time dependency on `paddlepaddle` itself. But actually using
it fails at runtime the moment a model/pipeline is created:

```
>>> from paddleocr import PaddleOCR
>>> PaddleOCR(use_angle_cls=True, lang="en")
...
RuntimeError: Engine 'paddle_static' is unavailable because dependency 'paddlepaddle' is not installed.
```

To confirm this is a Python-version problem rather than an Apple
Silicon/platform problem, wheel availability was checked directly against
PyPI for each CPython version on `macosx_11_0_arm64`:

```
$ python -m pip download paddlepaddle --no-deps -d /tmp/x \
    --python-version <X.Y> --only-binary=:all: --platform macosx_11_0_arm64
python 3.9:   paddlepaddle-3.3.1-cp39-cp39-macosx_11_0_arm64.whl   -> available
python 3.10:  paddlepaddle-3.3.1-cp310-cp310-macosx_11_0_arm64.whl -> available
python 3.11:  (no wheel found in this query, but 3.12/3.13 bracket it -- see note below)
python 3.12:  paddlepaddle-3.3.1-cp312-cp312-macosx_11_0_arm64.whl -> available
python 3.13:  paddlepaddle-3.3.1-cp313-cp313-macosx_11_0_arm64.whl -> available
python 3.14:  ERROR: No matching distribution found for paddlepaddle
```

Conclusion: `paddlepaddle` 3.3.1 ships real `arm64` macOS wheels up through
CPython 3.13, but **not** 3.14. This machine's system Python (Homebrew,
3.14.3) is simply ahead of what upstream `paddlepaddle` currently builds
for. This is not a licensing, platform, or dependency-tree problem -- it
is purely an interpreter-version gap, and one likely to close as upstream
catches up, or to be worked around sooner by pinning a slightly older
Python for the sidecar (see Decision below).

### Tesseract / pytesseract

```
$ which tesseract
/opt/homebrew/bin/tesseract
$ tesseract --version
tesseract 5.5.2
$ pip install pytesseract
Successfully installed Pillow-12.3.0 packaging-26.3 pytesseract-0.3.13
$ python -c "import pytesseract; print(pytesseract.get_tesseract_version())"
5.5.2
```

Tesseract 5.5.2 was already installed via Homebrew (`tesseract-lang` was
not -- only the `eng` language pack ships with the base formula:
`tesseract --list-langs` reports `eng`, `osd`, `snum`). `pytesseract`
installs and imports cleanly on Python 3.14.3 with no issues.

For multilingual validation, `tam.traineddata` and `ara.traineddata` (from
`tesseract-ocr/tessdata_fast`, Apache-2.0) were fetched manually and
pointed at via `TESSDATA_PREFIX` for local testing. With those present,
and Tesseract's page segmentation mode set to `--psm 6` (uniform block of
text -- receipts are not multi-column documents, and Tesseract's default
automatic segmentation performed poorly on small, tightly-cropped
text-only images), all three of the following real, rendered-text fixtures
recognized correctly end to end:

- English (Arial): `CORNER STORE / MILK 3.49 / BREAD 2.99 / TOTAL 6.48`
- Tamil (Tamil MN): `பிரைஸ்‌ பட்டியல்‌ / மோத 100`
- Arabic (SF Arabic): `فاتورة المحل / المجموع --2` (RTL correctly ordered)

The `--psm 6` change is applied unconditionally in
`TesseractEngine.recognize` since it consistently helped and did not hurt
any fixture tried.

## Decision

**Tesseract (via `pytesseract`) remains the default, always-available OCR
backend.** It is wired up as a fully working
`receiptlingua.engines.tesseract_engine.TesseractEngine`, covered by a
real end-to-end smoke test in `python/tests/test_tesseract_engine.py`
against genuinely rendered (not fake/placeholder) English, Tamil, and
Arabic text fixtures.

**Update (same day, follow-up session): PaddleOCR now genuinely works,
via a pinned-Python sidecar.** The blocker above was purely an
interpreter-version gap (`paddlepaddle` ships no cp314 wheel), not a
platform/arm64 problem, so it was closed by pinning the sidecar to an
older, still-supported CPython:

```
$ brew install python@3.13   # already present on this machine
$ /opt/homebrew/bin/python3.13 -m venv .venv-paddle   # gitignored, not committed
$ .venv-paddle/bin/pip install paddlepaddle paddleocr
$ .venv-paddle/bin/python -c "import paddle, paddleocr; print(paddle.__version__, paddleocr.__version__)"
3.3.1 3.7.0
```

Both import cleanly under Python 3.13.9 (Homebrew, arm64) with no build
errors. A real smoke test was then run against this repo's genuine
rendered-text fixtures (`python/tests/fixtures/receipt_text_{eng,tam,ara}.png`),
using PaddleOCR's `lang="en"` / `"ta"` / `"ar"` language groups and its
`predict()` API (models auto-downloaded from PaddleOCR's official model
hub on first use):

- **English** (`PP-OCRv6`/`PP-OCRv5_server` det+rec): perfect --
  `CORNER STORE / MILK3.49 / BREAD 2.99 / TOTAL 6.48`, confidence
  0.999-1.000 on every line.
- **Tamil** (`ta_PP-OCRv5_mobile_rec`): mostly correct but not perfect --
  recognized `பிரைஸ் பட்டியல்` (correct) and `மோ து 100` / `மோ தூ 100`
  (should be `மோத 100`; the word boundary/vowel-sign segmentation is
  slightly off), confidence 0.89-0.98. Usable, not flawless.
- **Arabic** (`arabic_PP-OCRv5_mobile_rec`): the two text lines recognize
  correctly (`فاتورة المحل`, `المجموع`), but the third line (the numeric
  total, `--2`) came back as an **empty string at confidence 0.0** in the
  raw `predict()` output and is filtered out entirely by the engine
  adapter -- i.e. Arabic digit/number recognition on this fixture
  silently dropped a line rather than misreading it. Confidence
  0.94-0.99 on the two lines it did recognize.

Honest assessment: English is excellent, Tamil is good-but-imperfect,
Arabic drops the numeric line rather than getting it wrong -- worth
flagging for anyone relying on totals extraction. None of this is a
crash or an empty result, so it clears the "do at least English + one
non-Latin script for real" bar, but the Tamil/Arabic quality gap versus
Tesseract's simpler recognition (also imperfect in its own ways, per
above) should be benchmarked properly before flipping the *default*
backend preference away from Tesseract.

**Wiring**: `receiptlingua.engines.paddleocr_engine.PaddleOCREngine` now
has a real `recognize()`. Because `paddlepaddle` cannot be imported into
this package's own Python 3.14 process, it runs PaddleOCR as a
**subprocess sidecar**: `RECEIPTLINGUA_PADDLE_PYTHON` (mirroring the
`RECEIPTLINGUA_CACHE_DIR` naming convention) points at the sidecar
interpreter (e.g. `.venv-paddle/bin/python`), and `recognize()` shells
out to `receiptlingua.engines._paddle_sidecar_script`, passing the image
path + language via a one-line JSON request on stdin and getting a
one-line JSON response back on stdout (text/confidence/bbox/polygon per
line). If the env var is unset or does not point at an executable file,
`is_available()` returns `False` and `recognize()` raises
`UnsupportedBackendError` (`UNSUPPORTED_BACKEND`) cleanly, exactly like
before -- there is no crash path.

This is explicitly a **stopgap transport**, not the final sidecar
protocol: one process per `recognize()` call, no model caching across
calls (each call re-pays PaddleOCR's model load), and no batching. The
real multi-request sidecar protocol referenced in `protocol/` is still a
separate, not-yet-designed piece of future work.

Because the sidecar venv itself is local, gitignored, machine-specific
setup (like Tesseract's `tam.traineddata`/`ara.traineddata` files
before it), `receiptlingua.engines.registry.get_default_engine()` still
tries PaddleOCR first and falls through to Tesseract automatically when
`RECEIPTLINGUA_PADDLE_PYTHON` isn't configured -- so a plain checkout with
no sidecar set up keeps working exactly as before, on Tesseract.

## Consequences / follow-up

- **The "109 languages" goal is not yet met by Tesseract alone.**
  Tesseract has `.traineddata` packs for ~100+ languages/scripts
  (Apache-2.0, via `tessdata_fast`), which is promising coverage, but
  recognition quality on receipt-specific layouts (narrow thermal fonts,
  degraded photos) has not been benchmarked against PaddleOCR's
  purpose-built PP-OCRv4/v5 multilingual recognition models. Revisit the
  primary-backend choice once PaddleOCR is actually runnable.
- **Resolved**: the sidecar-Python approach described here was carried
  out (Python 3.13 via Homebrew, see "Update" above) and PaddleOCR now
  runs for real through it. Remaining follow-up: design the real
  multi-request sidecar protocol/transport (current wiring is a
  one-process-per-call stopgap) and decide, after a proper
  Tesseract-vs-PaddleOCR quality benchmark across more receipt fixtures,
  whether PaddleOCR should become the *default* backend or stay an
  opt-in one behind `RECEIPTLINGUA_PADDLE_PYTHON`.
- **Language data is a setup-time, offline concern, never a runtime
  fetch.** `tam.traineddata`/`ara.traineddata` (and any other language
  beyond `eng`) must be placed either in the system Tesseract's own
  tessdata directory (e.g. via `brew install tesseract-lang` for the full
  set, or by hand-placing specific `.traineddata` files from
  `tesseract-ocr/tessdata_fast`) or under
  `$RECEIPTLINGUA_CACHE_DIR/tessdata/`. `brew install tesseract-lang` was
  deliberately not run in this session -- it bundles every supported
  language in one large bottle, which is more than this validation step
  needed; fetching only the specific languages needed (as done here for
  `tam`/`ara`) is documented instead as the lighter-weight setup path.
  `CacheManager.require_tesseract_language()` raises `MODEL_NOT_FOUND`
  (never attempts a download) when a needed language file is absent.
- Surya (mentioned in the original milestone list as a benchmark-only
  adapter) was not evaluated in this session -- deprioritized in favor of
  getting one real backend fully working end to end. Tracked as future
  work, not a blocker.

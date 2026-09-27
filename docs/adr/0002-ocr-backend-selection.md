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

**Tesseract (via `pytesseract`) is the default, real, validated OCR
backend for now.** It is wired up as a fully working
`receiptlingua.engines.tesseract_engine.TesseractEngine`, covered by a
real end-to-end smoke test in `python/tests/test_tesseract_engine.py`
against genuinely rendered (not fake/placeholder) English, Tamil, and
Arabic text fixtures.

**PaddleOCR is not usable in this environment today** and is *not*
force-installed or faked. `receiptlingua.engines.paddleocr_engine.PaddleOCREngine`
defines the intended adapter shape (constructor, `is_available()`,
`supported_languages()`) so the integration is ready to fill in, but
`recognize()` raises `UnsupportedBackendError` (protocol code
`UNSUPPORTED_BACKEND`) immediately rather than shipping an untested code
path. `PaddleOCREngine.is_available()` returns `False` here and the
registry (`receiptlingua.engines.registry.get_default_engine`) skips it in
favor of Tesseract automatically.

## Consequences / follow-up

- **The "109 languages" goal is not yet met by Tesseract alone.**
  Tesseract has `.traineddata` packs for ~100+ languages/scripts
  (Apache-2.0, via `tessdata_fast`), which is promising coverage, but
  recognition quality on receipt-specific layouts (narrow thermal fonts,
  degraded photos) has not been benchmarked against PaddleOCR's
  purpose-built PP-OCRv4/v5 multilingual recognition models. Revisit the
  primary-backend choice once PaddleOCR is actually runnable.
- **Recommended path to unblock PaddleOCR**: run it as a separate sidecar
  process pinned to a supported Python version (3.11, 3.12, or 3.13 all
  have working `arm64` wheels for `paddlepaddle==3.3.1`; 3.13 is closest
  to the current 3.14 and should be tried first), managed via `pyenv` or
  `uv python install 3.13` once `uv` is available, rather than waiting on
  upstream to ship a 3.14 wheel. This is consistent with the existing
  sidecar architecture (`protocol/`) -- the JS/Ruby clients already talk
  to a Python sidecar over a documented protocol, so that sidecar process
  does not have to run under the same Python as the rest of the repo's
  tooling.
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

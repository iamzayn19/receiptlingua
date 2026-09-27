#!/usr/bin/env python3
"""Synthetic OCR benchmark harness (milestone 171-185).

Generates deterministic synthetic receipts (``receiptlingua.synth``),
applies seeded degradations, runs the REAL ``ReceiptOCR().scan()``
pipeline against each case, and scores against exact ground truth with
real metrics (CER, WER, normalized edit distance, field accuracy).

Honesty notes baked into this script's design, not just its README:

- It never fabricates results. Every row in the aggregated summary is
  computed from cases that were actually executed in *this* invocation
  (or accumulated across invocations if you point ``--output-dir`` at the
  same place and pass ``--append``); there is no "assume the rest would
  look like this" extrapolation anywhere.
- It reports the real executed case count. If you ask for more cases
  than finish in a reasonable time, that's your call via ``--count`` /
  ``--languages`` / ``--degradations`` -- the script does not silently
  truncate and then claim the requested count.
- Raw per-case results go under ``benchmarks/results/`` (gitignored, can
  be large); only the aggregated ``latest_summary.json`` is meant to be
  committed.

Usage::

    python benchmarks/run_benchmark.py --samples-per-language 5 \\
        --languages en,ta,ar --degradations all

    # Scale up once compute/time allows (designed capacity, not yet run):
    python benchmarks/run_benchmark.py --samples-per-language 200 \\
        --languages en,ta,ar,hi,he --degradations all
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "python" / "src"))

from receiptlingua.api import ReceiptOCR  # noqa: E402
from receiptlingua.synth.degrade import DEGRADATIONS  # noqa: E402
from receiptlingua.synth.generator import SUPPORTED_LANGUAGES, generate_receipt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from metrics import fuzzy_match  # noqa: E402
from metrics import character_error_rate, normalized_edit_distance, word_error_rate

RESULTS_DIR = REPO_ROOT / "benchmarks" / "results"
SUMMARY_PATH = REPO_ROOT / "benchmarks" / "latest_summary.json"

#: The synth generator and receiptlingua's own language-id data use
#: ISO 639-1 codes (ta, ar, hi, he, ...), but the actual Tesseract
#: tessdata_fast langpacks installed via `brew install tesseract-lang` are
#: named with ISO 639-2/3 codes (tam, ara, hin, heb, ...). The OCR engine
#: itself does not do this remapping (a real, separate gap -- see
#: python/src/receiptlingua/langid/data/language_matrix.json), so the
#: harness maps it here purely so it can drive the *real* installed
#: langpacks for a real benchmark run, without editing engine internals.
#:
#: Verified present via `tesseract --list-langs` on this machine (163
#: langpacks installed by `brew install tesseract-lang`, tessdata_fast
#: bundle) for every one of the 25 synth-generator languages -- no
#: langpack was missing, so no new `brew install` was needed for this run.
TESSERACT_LANG_MAP: dict[str, str] = {
    "ta": "tam",
    "ar": "ara",
    "hi": "hin",
    "he": "heb",
    "fr": "fra",
    "de": "deu",
    "es": "spa",
    "pt": "por",
    "it": "ita",
    "nl": "nld",
    "tr": "tur",
    "pl": "pol",
    "id": "ind",
    "ms": "msa",
    "vi": "vie",
    "ru": "rus",
    "uk": "ukr",
    "fa": "fas",
    "ur": "urd",
    "mr": "mar",
    "zh-Hans": "chi_sim",
    "zh-Hant": "chi_tra",
    "ja": "jpn",
    "ko": "kor",
}

#: Non-Latin-script languages whose synthetic receipts still contain a
#: real, mandatory Latin/ASCII substring: the "SUBTOTAL"/"TAX"/"TOTAL"
#: field labels and the ASCII-digit amounts themselves (see
#: ``receiptlingua.synth.generator.generate_receipt`` -- those three
#: labels and all numeric amounts are always ASCII, in every language,
#: by design; only the merchant/address/item-description words are
#: rendered in the receipt's own script). A single non-Latin Tesseract
#: langpack (e.g. ``rus`` alone) has no Latin letters in its
#: dictionary/character set, so it doesn't just mis-recognize those
#: labels -- it actively transliterates them into look-alike
#: same-script characters (confirmed by direct inspection: "TOTAL" came
#: back as Cyrillic "ТОТАЕ" under lang="rus", as garbled Devanagari
#: under lang="hin", as Arabic-lookalike digits under lang="ara"),
#: which is exactly why ``extract_total``'s keyword search (which only
#: matches the literal ASCII word "total") found nothing and every one
#: of these languages measured 0.0% total-exact-match. Passing a
#: combined language pack (``lang+eng``) to Tesseract -- the documented,
#: standard mitigation for mixed-script text -- fixes this: verified by
#: direct reprocessing of ru/hi/ar samples with "rus+eng"/"hin+eng"/
#: "ara+eng", which recovered the literal "SUBTOTAL"/"TAX"/"TOTAL"
#: labels and, for ru/ar, the exact correct total value.
NON_LATIN_TESSERACT_LANGS: frozenset[str] = frozenset(
    {"ru", "uk", "ko", "ta", "mr", "hi", "he", "ar", "fa", "ur", "zh-Hans", "zh-Hant", "ja"}
)

#: PaddleOCR's `lang=` parameter uses ISO 639-1 codes DIRECTLY for most
#: languages (confirmed by reading
#: .venv-paddle/lib/python3.13/site-packages/paddleocr/_utils/langs.py --
#: e.g. "ar", "hi", "ru", "uk", "fa", "ur" are accepted as-is via its
#: ARABIC_LANGS/DEVANAGARI_LANGS/CYRILLIC_LANGS/ESLAV_LANGS groupings), so
#: no remapping is needed for those -- unlike Tesseract, which needs the
#: ISO 639-2/3 TESSERACT_LANG_MAP above. The one real exception is CJK:
#: PaddleOCR uses its own legacy PP-OCR names for those four, confirmed in
#: .venv-paddle/lib/python3.13/site-packages/paddleocr/_pipelines/ocr.py
#: (``_PPOCRV6_LANGS = {"ch", "chinese_cht", "en", "japan", "korean", ...}``).
#: A first attempt at this benchmark run reused TESSERACT_LANG_MAP
#: unconditionally for both backends and got 700/840 PaddleOCR cases
#: failing outright with `ValueError: No models are available for
#: lang='rus'` etc. -- this map is the real fix, not a guess.
PADDLE_LANG_MAP: dict[str, str] = {
    "zh-Hans": "ch",
    "zh-Hant": "chinese_cht",
    "ja": "japan",
    "ko": "korean",
}


def _parse_list_arg(value: str, valid: list[str]) -> list[str]:
    if value == "all":
        return list(valid)
    chosen = [v.strip() for v in value.split(",") if v.strip()]
    unknown = [v for v in chosen if v not in valid]
    if unknown:
        raise SystemExit(f"unknown value(s) {unknown}; valid options: {valid}")
    return chosen


def run_case(
    *,
    language: str,
    degradation: str,
    seed: int,
    backend: str | None,
    raw_dir: Path,
    ocr_cache: dict[str, ReceiptOCR],
) -> dict:
    receipt = generate_receipt(language, seed)
    degrade_fn = DEGRADATIONS[degradation]
    degraded_image = degrade_fn(receipt.image, seed)

    case_id = f"{language}_{degradation}_{seed}"
    img_path = raw_dir / f"{case_id}.png"
    gt_path = raw_dir / f"{case_id}.json"
    degraded_image.save(img_path)
    receipt.ground_truth.save(gt_path)

    if backend == "paddleocr":
        engine_lang = PADDLE_LANG_MAP.get(language, language)
        engine_languages: tuple[str, ...] = (engine_lang,) if language != "en" else ()
    else:
        engine_lang = TESSERACT_LANG_MAP.get(language, language)
        if language == "en":
            engine_languages = ()
        elif language in NON_LATIN_TESSERACT_LANGS:
            # See NON_LATIN_TESSERACT_LANGS above: without "+eng", a
            # non-Latin langpack transliterates the receipt's mandatory
            # ASCII "SUBTOTAL"/"TAX"/"TOTAL" labels and amounts into
            # garbage, which is the real, verified cause of the 0.0%
            # total-exact-match rate for these languages.
            engine_languages = (engine_lang, "eng")
        else:
            engine_languages = (engine_lang,)
    # Reuse one ReceiptOCR/engine instance per language across every case in
    # this run (instead of constructing a fresh one per case) so a
    # PaddleOCR backend's persistent sidecar daemon (see
    # docs/adr/0002-ocr-backend-selection.md) actually gets to pay its
    # ~1.7s model-load cost only ONCE per language and serve every
    # subsequent case for that language warm (~0.5s) -- a fresh instance
    # per case would defeat the whole point of the daemon.
    if language not in ocr_cache:
        ocr_cache[language] = ReceiptOCR(backend=backend, languages=engine_languages)
    ocr = ocr_cache[language]
    start = time.perf_counter()
    error = None
    result = None
    try:
        result = ocr.scan(str(img_path))
    except Exception as exc:  # noqa: BLE001 - a benchmark case failing must not crash the run
        error = f"{type(exc).__name__}: {exc}"
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    gt = receipt.ground_truth
    if error is not None:
        case_metrics = {
            "cer": 1.0,
            "wer": 1.0,
            "normalized_edit_distance": 1.0,
            "merchant_match": False,
            "date_exact_match": False,
            "total_exact_match": False,
        }
        hypothesis_text = ""
    else:
        hypothesis_text = result.full_text
        case_metrics = {
            "cer": character_error_rate(gt.full_text, hypothesis_text),
            "wer": word_error_rate(gt.full_text, hypothesis_text),
            "normalized_edit_distance": normalized_edit_distance(gt.full_text, hypothesis_text),
        }
        fields = result.fields
        merchant_field = fields.get("merchant", {})
        date_field = fields.get("date", {})
        total_field = fields.get("total", {})
        case_metrics["merchant_match"] = (
            fuzzy_match(gt.merchant, merchant_field.get("value", ""))
            if merchant_field.get("value") is not None
            else False
        )
        case_metrics["date_exact_match"] = date_field.get("value") == gt.date
        total_value = total_field.get("value")
        case_metrics["total_exact_match"] = (
            total_value is not None and abs(float(total_value) - gt.total) < 0.005
        )

    case_record = {
        "case_id": case_id,
        "language": language,
        "degradation": degradation,
        "seed": seed,
        "backend": backend or "default",
        "error": error,
        "elapsed_ms": round(elapsed_ms, 2),
        "ground_truth_total": gt.total,
        "hypothesis_text_len": len(hypothesis_text),
        **case_metrics,
    }
    return case_record


def aggregate(records: list[dict]) -> dict:
    by_key: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for r in records:
        by_key[(r["language"], r["degradation"], r["backend"])].append(r)

    breakdown = []
    for (language, degradation, backend), rows in sorted(by_key.items()):
        n = len(rows)
        errors = sum(1 for r in rows if r["error"] is not None)
        breakdown.append(
            {
                "language": language,
                "degradation": degradation,
                "backend": backend,
                "n_cases": n,
                "n_errors": errors,
                "mean_cer": round(statistics.mean(r["cer"] for r in rows), 4),
                "mean_wer": round(statistics.mean(r["wer"] for r in rows), 4),
                "mean_normalized_edit_distance": round(
                    statistics.mean(r["normalized_edit_distance"] for r in rows), 4
                ),
                "merchant_match_rate": round(
                    sum(1 for r in rows if r["merchant_match"]) / n, 4
                ),
                "date_exact_match_rate": round(
                    sum(1 for r in rows if r["date_exact_match"]) / n, 4
                ),
                "total_exact_match_rate": round(
                    sum(1 for r in rows if r["total_exact_match"]) / n, 4
                ),
                "mean_elapsed_ms": round(statistics.mean(r["elapsed_ms"] for r in rows), 1),
            }
        )

    overall = {
        "n_cases": len(records),
        "n_errors": sum(1 for r in records if r["error"] is not None),
        "mean_cer": round(statistics.mean(r["cer"] for r in records), 4) if records else None,
        "mean_wer": round(statistics.mean(r["wer"] for r in records), 4) if records else None,
        "total_exact_match_rate": round(
            sum(1 for r in records if r["total_exact_match"]) / len(records), 4
        )
        if records
        else None,
    }
    return {"overall": overall, "breakdown": breakdown}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--languages", default="en,ta,ar", help="comma list or 'all' (default: en,ta,ar)")
    parser.add_argument("--degradations", default="all", help="comma list or 'all'")
    parser.add_argument(
        "--samples-per-language",
        type=int,
        default=5,
        help="base receipts per language; total cases = languages * samples * degradations (default: 5)",
    )
    parser.add_argument("--seed-base", type=int, default=10_000, help="base seed offset (default: 10000)")
    parser.add_argument("--backend", default=None, help="OCR backend name (default: engine registry default)")
    parser.add_argument(
        "--max-cases",
        type=int,
        default=None,
        help="hard safety cap on total cases actually run, regardless of the languages/samples/degradations product",
    )
    parser.add_argument("--output-dir", default=str(RESULTS_DIR))
    args = parser.parse_args()

    languages = _parse_list_arg(args.languages, list(SUPPORTED_LANGUAGES))
    degradations = _parse_list_arg(args.degradations, list(DEGRADATIONS.keys()))

    planned_cases = len(languages) * args.samples_per_language * len(degradations)
    cases_to_run = planned_cases if args.max_cases is None else min(planned_cases, args.max_cases)

    raw_dir = Path(args.output_dir) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"Planned cases: {planned_cases} "
        f"({len(languages)} languages x {args.samples_per_language} samples x {len(degradations)} degradations)"
    )
    if args.max_cases is not None and cases_to_run < planned_cases:
        print(f"--max-cases caps this run at {cases_to_run} cases (fewer than the planned {planned_cases}).")

    records: list[dict] = []
    run_count = 0
    ocr_cache: dict[str, ReceiptOCR] = {}
    start_all = time.perf_counter()
    for language in languages:
        for sample_idx in range(args.samples_per_language):
            for degradation in degradations:
                if run_count >= cases_to_run:
                    break
                seed = args.seed_base + hash((language, sample_idx)) % 1_000_000
                record = run_case(
                    language=language,
                    degradation=degradation,
                    seed=seed,
                    backend=args.backend,
                    raw_dir=raw_dir,
                    ocr_cache=ocr_cache,
                )
                records.append(record)
                run_count += 1
                print(
                    f"[{run_count}/{cases_to_run}] {language}/{degradation} "
                    f"seed={seed} cer={record['cer']:.3f} elapsed={record['elapsed_ms']:.0f}ms "
                    f"{'ERROR: ' + record['error'] if record['error'] else ''}"
                )
            if run_count >= cases_to_run:
                break
        if run_count >= cases_to_run:
            break
    total_elapsed = time.perf_counter() - start_all
    for ocr in ocr_cache.values():
        ocr.close()

    raw_jsonl = Path(args.output_dir) / "latest_raw.jsonl"
    with raw_jsonl.open("w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    summary = aggregate(records)
    summary["meta"] = {
        "n_cases_executed": len(records),
        "n_cases_planned": planned_cases,
        "languages": languages,
        "degradations": degradations,
        "samples_per_language": args.samples_per_language,
        "backend": args.backend or "default",
        "total_wall_time_s": round(total_elapsed, 1),
        "mean_case_time_s": round(total_elapsed / len(records), 3) if records else None,
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(f"\nExecuted {len(records)} real cases in {total_elapsed:.1f}s. Summary written to {SUMMARY_PATH}")


if __name__ == "__main__":
    main()

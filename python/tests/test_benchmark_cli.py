"""Regression tests for benchmark orchestration without running OCR."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

BENCHMARKS = Path(__file__).resolve().parents[2] / "benchmarks"
sys.path.insert(0, str(BENCHMARKS))

from run_benchmark import _parse_list_arg, case_seed, main  # noqa: E402
import run_benchmark as harness  # noqa: E402


def test_case_seed_is_stable_across_python_processes():
    command = "from run_benchmark import case_seed; print(case_seed('en', 2, 10000))"
    seeds = [
        subprocess.check_output(
            [sys.executable, "-c", command],
            env={**os.environ, "PYTHONHASHSEED": value, "PYTHONPATH": str(BENCHMARKS)},
            text=True,
        ).strip()
        for value in ["1", "2"]
    ]
    assert seeds == [str(case_seed("en", 2, 10000))] * 2


@pytest.mark.parametrize("value", ["", " , "])
def test_empty_selection_is_rejected(value):
    with pytest.raises(SystemExit, match="at least one"):
        _parse_list_arg(value, ["en"])


def test_duplicate_selections_run_only_once():
    assert _parse_list_arg("en,en", ["en"]) == ["en"]


@pytest.mark.parametrize("option", ["--samples-per-language", "--max-cases"])
@pytest.mark.parametrize("count", ["0", "-1"])
def test_nonpositive_counts_fail_before_ocr(monkeypatch, capsys, option, count):
    monkeypatch.setattr(sys, "argv", ["benchmark", option, count])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    assert f"{option} must be positive" in capsys.readouterr().err


@pytest.fixture
def fake_case(monkeypatch):
    def run(**kwargs):
        return {
            "language": kwargs["language"], "degradation": kwargs["degradation"],
            "backend": "default", "error": None, "cer": 0.0, "wer": 0.0,
            "normalized_edit_distance": 0.0, "merchant_match": True,
            "date_exact_match": True, "total_exact_match": True, "elapsed_ms": 1.0,
        }
    monkeypatch.setattr(harness, "run_case", run)


def test_custom_output_keeps_summary_outside_checkout(monkeypatch, tmp_path, fake_case):
    monkeypatch.setattr(sys, "argv", [
        "benchmark", "--languages", "en", "--degradations", "clean",
        "--samples-per-language", "1", "--output-dir", str(tmp_path),
    ])
    main()
    summary = json.loads((tmp_path / "latest_summary.json").read_text())
    assert summary["overall"]["n_cases"] == 1
    assert (tmp_path / "latest_raw.jsonl").exists()


def test_engine_initialization_error_is_recorded(monkeypatch, tmp_path):
    def unavailable(**kwargs):
        raise RuntimeError("OCR backend unavailable")

    monkeypatch.setattr(harness, "ReceiptOCR", unavailable)
    record = harness.run_case(
        language="en", degradation="clean", seed=1, backend=None,
        raw_dir=tmp_path, ocr_cache={},
    )
    assert record["error"] == "RuntimeError: OCR backend unavailable"
    assert record["total_exact_match"] is False
    assert (tmp_path / "en_clean_1.json").exists()

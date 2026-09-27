"""End-to-end smoke test for benchmarks/run_benchmark.py.

This is deliberately tiny (a handful of cases) and separate from any
large real benchmark run: it exists to prove the harness itself (synth
generation -> degradation -> real ReceiptOCR().scan() -> metrics ->
aggregated summary) is wired correctly, not to produce a meaningful
accuracy number.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "benchmarks"))

from run_benchmark import aggregate, run_case  # noqa: E402


def test_run_case_produces_expected_shape(tmp_path):
    record = run_case(language="en", degradation="clean", seed=555, backend=None, raw_dir=tmp_path)
    assert record["language"] == "en"
    assert record["degradation"] == "clean"
    assert 0.0 <= record["cer"]
    assert 0.0 <= record["wer"]
    assert record["error"] is None
    # Raw case artifacts (image + ground truth) were actually written.
    assert (tmp_path / "en_clean_555.png").exists()
    assert (tmp_path / "en_clean_555.json").exists()
    gt = json.loads((tmp_path / "en_clean_555.json").read_text())
    assert gt["merchant"]


def test_run_case_with_degradation(tmp_path):
    record = run_case(
        language="en", degradation="gaussian_blur", seed=556, backend=None, raw_dir=tmp_path
    )
    assert record["error"] is None
    assert record["degradation"] == "gaussian_blur"


def test_aggregate_summary_shape(tmp_path):
    records = [
        run_case(language="en", degradation=deg, seed=600 + i, backend=None, raw_dir=tmp_path)
        for i, deg in enumerate(["clean", "gaussian_blur", "gaussian_noise"])
    ]
    summary = aggregate(records)
    assert summary["overall"]["n_cases"] == 3
    assert len(summary["breakdown"]) == 3
    for row in summary["breakdown"]:
        assert "mean_cer" in row
        assert "total_exact_match_rate" in row
        assert row["n_cases"] == 1


def test_harness_smoke_five_cases(tmp_path):
    """A tiny (5-case) full run through run_case, distinct from any large
    real benchmark batch, to prove the harness end-to-end."""
    records = [
        run_case(language="en", degradation=deg, seed=700 + i, backend=None, raw_dir=tmp_path)
        for i, deg in enumerate(["clean", "rotation", "gaussian_blur", "jpeg_compression", "crop"])
    ]
    assert len(records) == 5
    assert all(r["error"] is None for r in records)
    summary = aggregate(records)
    assert summary["overall"]["n_cases"] == 5

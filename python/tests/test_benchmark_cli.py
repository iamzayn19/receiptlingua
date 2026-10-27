"""Regression tests for benchmark orchestration without running OCR."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

BENCHMARKS = Path(__file__).resolve().parents[2] / "benchmarks"
sys.path.insert(0, str(BENCHMARKS))

from run_benchmark import _parse_list_arg, case_seed, main  # noqa: E402


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

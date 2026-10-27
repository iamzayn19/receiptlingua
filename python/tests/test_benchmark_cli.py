"""Regression tests for benchmark orchestration without running OCR."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

BENCHMARKS = Path(__file__).resolve().parents[2] / "benchmarks"
sys.path.insert(0, str(BENCHMARKS))

from run_benchmark import case_seed  # noqa: E402


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

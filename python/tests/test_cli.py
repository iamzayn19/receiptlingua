"""Integration tests for the ``receiptlingua`` CLI.

Invoked via ``python -m receiptlingua.cli`` in a subprocess (not by
calling ``main()`` in-process) so this exercises the same code path a
real installed ``receiptlingua`` console script would, including argv
parsing and process exit codes.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from receiptlingua.engines.tesseract_engine import TesseractEngine

FIXTURES_DIR = Path(__file__).parent / "fixtures"
_tesseract = TesseractEngine()


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "receiptlingua.cli", *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_version():
    result = _run("--version")
    assert result.returncode == 0
    assert "receiptlingua" in result.stdout


def test_languages_text_output():
    result = _run("languages")
    assert result.returncode == 0
    assert "model_supported" in result.stdout
    assert "en" in result.stdout


def test_languages_json_output():
    result = _run("languages", "--json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert isinstance(data, list)
    assert any(e["code"] == "en" for e in data)


def test_doctor_text_output():
    result = _run("doctor")
    assert result.returncode == 0
    assert "OS:" in result.stdout
    assert "Backends:" in result.stdout
    # Never leak the actual value of a sidecar/env-var-shaped secret.
    assert "RECEIPTLINGUA_PADDLE_PYTHON" in result.stdout


def test_doctor_json_output():
    result = _run("doctor", "--json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "os" in data and "backends" in data
    assert "paddle_sidecar_env_var_set" in data


def test_cache_info():
    result = _run("cache", "info")
    assert result.returncode == 0
    assert "cache dir" in result.stdout


def test_models():
    result = _run("models")
    assert result.returncode == 0
    assert "tessdata" in result.stdout


def test_benchmark_is_honest_stub():
    result = _run("benchmark")
    assert result.returncode == 0
    assert "not yet implemented" in result.stdout


@pytest.mark.skipif(not _tesseract.is_available(), reason="tesseract not available")
def test_scan_json_output_matches_schema():
    result = _run("scan", str(FIXTURES_DIR / "receipt_text_eng.png"), "--json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["schema_version"] == "0.1.0"
    assert data["full_text"].strip() != ""


@pytest.mark.skipif(not _tesseract.is_available(), reason="tesseract not available")
def test_scan_text_output():
    result = _run("scan", str(FIXTURES_DIR / "receipt_text_eng.png"))
    assert result.returncode == 0
    assert "engine:" in result.stdout
    assert "--- text ---" in result.stdout


def test_scan_missing_file_exits_nonzero_with_error_code():
    result = _run("scan", "does/not/exist.png", "--json")
    assert result.returncode == 1
    data = json.loads(result.stdout)
    assert data["error"]["code"] == "INVALID_IMAGE"

"""Backend capability probing.

Deliberately small and honest: this reports what is actually usable in
the current process/environment right now, not a speculative hardware
abstraction layer. Only Tesseract is wired up as a real backend today
(see docs/adr/0002-ocr-backend-selection.md), and Tesseract is CPU-only,
so there is no MPS/CUDA probing here yet -- that gets added if/when a
torch- or paddle-based backend actually becomes usable in this
environment, per the "build only what the chosen backend needs" guidance.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class BackendCapability:
    name: str
    available: bool
    reason: str


@dataclass(frozen=True)
class CapabilityReport:
    cpu_count: int
    backends: tuple[BackendCapability, ...]

    def is_available(self, backend: str) -> bool:
        return any(b.name == backend and b.available for b in self.backends)


def _probe_tesseract() -> BackendCapability:
    binary = shutil.which("tesseract")
    if binary is None:
        return BackendCapability("tesseract", False, "tesseract binary not found on PATH")

    if importlib.util.find_spec("pytesseract") is None:
        return BackendCapability("tesseract", False, "pytesseract package not installed")

    try:
        result = subprocess.run(
            [binary, "--version"], capture_output=True, text=True, timeout=5, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return BackendCapability("tesseract", False, f"tesseract --version failed: {exc}")

    if result.returncode != 0:
        return BackendCapability("tesseract", False, f"tesseract --version exited {result.returncode}")

    version_line = result.stdout.splitlines()[0] if result.stdout else "unknown version"
    return BackendCapability("tesseract", True, version_line)


def _probe_paddleocr() -> BackendCapability:
    if importlib.util.find_spec("paddle") is None or importlib.util.find_spec("paddleocr") is None:
        return BackendCapability(
            "paddleocr",
            False,
            f"paddlepaddle/paddleocr not importable in this Python environment "
            f"(python {sys.version.split()[0]})",
        )
    return BackendCapability("paddleocr", True, "paddle and paddleocr importable")


def probe_capabilities() -> CapabilityReport:
    """Probe what's actually usable right now. Safe to call repeatedly; no caching."""
    cpu_count = os.cpu_count() or 1
    backends = (_probe_tesseract(), _probe_paddleocr())
    return CapabilityReport(cpu_count=cpu_count, backends=backends)

#!/usr/bin/env python3
"""Generate a CycloneDX software bill of materials for the Python package.

Not wired into every CI run (a SBOM is a release-time artifact, not a
per-PR check). Run manually before cutting a release:

    cd python
    python -m pip install -e ".[dev]" cyclonedx-bom
    python scripts/generate_sbom.py

Writes `python/sbom.json` (CycloneDX 1.5 JSON), built from the
requirements declared in pyproject.toml -- not from a full installed
virtualenv snapshot -- so it reflects the declared dependency set,
including the optional `paddleocr` extra path, rather than whatever
happens to be installed in a given dev environment. If `cyclonedx-py`
is not importable this script falls back to an honest, minimal SBOM-
shaped JSON document derived from `pip freeze` -- clearly labeled as a
fallback in the `metadata.properties` field, never disguised as a full
CycloneDX component graph with license/PURL metadata it doesn't
actually have.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "sbom.json"


def _try_cyclonedx() -> bool:
    try:
        import cyclonedx_py  # noqa: F401
    except ImportError:
        return False

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cyclonedx_py",
            "requirements",
            "-",
            "--output-format",
            "json",
            "--output-file",
            str(OUTPUT),
        ],
        input=_pip_freeze(),
        text=True,
        cwd=ROOT,
    )
    return result.returncode == 0


def _pip_freeze() -> str:
    return subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _fallback_sbom() -> None:
    """Honest fallback: a pip-freeze-derived, SBOM-shaped document.

    This is NOT a real CycloneDX document with resolved PURLs/licenses --
    it is explicitly labeled as a fallback so nobody downstream mistakes
    it for one.
    """
    freeze_lines = [line for line in _pip_freeze().splitlines() if line and "==" in line]
    components = []
    for line in freeze_lines:
        name, _, version = line.partition("==")
        components.append({"type": "library", "name": name, "version": version})

    doc = {
        "bomFormat": "CycloneDX-fallback",
        "specVersion": "not-a-real-cyclonedx-document",
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "properties": [
                {
                    "name": "receiptlingua:sbom-generator",
                    "value": (
                        "fallback pip-freeze snapshot -- cyclonedx-py was not "
                        "importable when this was generated; install "
                        "`cyclonedx-bom` and re-run scripts/generate_sbom.py "
                        "for a real CycloneDX SBOM"
                    ),
                }
            ],
        },
        "components": components,
    }
    OUTPUT.write_text(json.dumps(doc, indent=2) + "\n")


def main() -> None:
    if _try_cyclonedx():
        print(f"Wrote CycloneDX SBOM to {OUTPUT}")
        return

    print(
        "cyclonedx-py not available; writing an honest pip-freeze-derived "
        "fallback (not a real CycloneDX document) instead.",
        file=sys.stderr,
    )
    _fallback_sbom()
    print(f"Wrote fallback SBOM-shaped document to {OUTPUT}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Validate every fixture in protocol/fixtures/ against its schema.

Usage:
    python3 protocol/validate_fixtures.py

A fixture is matched to a schema by convention:
  - a filename containing "error" validates against schema/error.schema.json
  - everything else validates against schema/response.schema.json

Exits non-zero if any fixture fails validation, or if a fixture's
top-level shape doesn't match either schema's expected form.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROTOCOL_DIR = Path(__file__).resolve().parent
SCHEMA_DIR = PROTOCOL_DIR / "schema"
FIXTURES_DIR = PROTOCOL_DIR / "fixtures"

try:
    import jsonschema
except ImportError:
    print(
        "The 'jsonschema' package is required to validate fixtures.\n"
        "Install it with:\n\n    pip install jsonschema\n\n"
        "or, in a throwaway virtualenv:\n\n"
        "    python3 -m venv .venv && .venv/bin/pip install jsonschema "
        "&& .venv/bin/python protocol/validate_fixtures.py\n",
        file=sys.stderr,
    )
    sys.exit(1)


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def schema_for(fixture_path: Path) -> Path:
    if "error" in fixture_path.stem:
        return SCHEMA_DIR / "error.schema.json"
    return SCHEMA_DIR / "response.schema.json"


def main() -> int:
    if not FIXTURES_DIR.is_dir():
        print(f"No fixtures directory at {FIXTURES_DIR}", file=sys.stderr)
        return 1

    fixture_paths = sorted(FIXTURES_DIR.glob("*.json"))
    if not fixture_paths:
        print(f"No fixture files found in {FIXTURES_DIR}", file=sys.stderr)
        return 1

    failures = 0
    for fixture_path in fixture_paths:
        schema_path = schema_for(fixture_path)
        schema = load_json(schema_path)
        instance = load_json(fixture_path)

        validator = jsonschema.Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(instance), key=lambda e: e.path)

        if errors:
            failures += 1
            print(f"FAIL  {fixture_path.name}  (against {schema_path.name})")
            for err in errors:
                loc = "/".join(str(p) for p in err.path) or "<root>"
                print(f"        at {loc}: {err.message}")
        else:
            print(f"OK    {fixture_path.name}  (against {schema_path.name})")

    if failures:
        print(f"\n{failures} of {len(fixture_paths)} fixture(s) failed validation.")
        return 1

    print(f"\nAll {len(fixture_paths)} fixture(s) valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

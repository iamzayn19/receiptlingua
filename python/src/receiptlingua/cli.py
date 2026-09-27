"""``receiptlingua`` command-line interface.

Uses stdlib ``argparse`` rather than click/typer: this project has kept
every prior milestone's dependency list minimal and justified (numpy,
pillow, opencv-python-headless, pytesseract, regex, py3langid -- see
``pyproject.toml``), and ``click`` is not already a dependency anywhere
in the tree. ``argparse` needs zero new dependencies and the CLI surface
here (a handful of subcommands, a few flags each) does not need more
than it offers.
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import sys
from typing import Any

from receiptlingua import ReceiptOCR, ReceiptOCRError, __version__
from receiptlingua.engines.cache import CacheManager
from receiptlingua.engines.capabilities import probe_capabilities
from receiptlingua.engines.mode import Mode
from receiptlingua.engines.paddleocr_engine import PADDLE_PYTHON_ENV_VAR
from receiptlingua.langid.matrix import load_matrix


def _print_json(obj: Any) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def cmd_scan(args: argparse.Namespace) -> int:
    languages = tuple(args.lang.split(",")) if args.lang and args.lang != "auto" else None
    # A single `receiptlingua scan` invocation only ever does one scan, so
    # there's no repeated-call benefit from the sidecar daemon here -- but
    # we still must not leave it running after the process is "done";
    # ReceiptOCR is used as a context manager purely for that cleanup.
    with ReceiptOCR(mode=args.mode, languages=languages) as ocr:
        try:
            result = ocr.scan(args.path)
        except ReceiptOCRError as exc:
            if args.json:
                _print_json(exc.to_dict())
            else:
                print(f"error: [{exc.code}] {exc.message}", file=sys.stderr)
            return 1

    if args.json:
        print(result.to_json())
    else:
        print(f"engine: {result.engine} ({result.engine_version}), mode: {result.mode}")
        print(f"processing_time_ms: {result.processing_time_ms}")
        # tag_document() (receiptlingua.langid.tagging) returns every
        # language with any non-zero vote across all lines, which for
        # short receipt text can be a very long, mostly-noise tail --
        # the full list is still in result.languages / --json, but the
        # human-readable view only shows the confident head.
        top_langs = [lg for lg in result.languages if lg["confidence"] >= 0.05][:5]
        langs = (
            ", ".join(f"{lg['code']}:{lg['confidence']}" for lg in top_langs)
            or "(none confident)"
        )
        extra = len(result.languages) - len(top_langs)
        suffix = f"  (+{extra} more, low-confidence)" if extra > 0 else ""
        print(f"languages: {langs}{suffix}")
        print(f"scripts: {', '.join(result.scripts) or '(none)'}")
        print("--- text ---")
        print(result.full_text)
        print("--- fields ---")
        for name, value in result.fields.items():
            if name == "line_items":
                continue
            print(f"  {name}: {value}")
        if result.fields.get("line_items"):
            print(f"  line_items: {len(result.fields['line_items'])} item(s)")
        if result.warnings:
            print("--- warnings ---")
            for w in result.warnings:
                print(f"  - {w}")
    return 0


def cmd_languages(args: argparse.Namespace) -> int:
    entries = load_matrix()
    if args.json:
        _print_json(
            [
                {
                    "code": e.code,
                    "name": e.name,
                    "script": e.script,
                    "model_supported": e.model_supported,
                    "receipt_verified": e.receipt_verified,
                    "rtl": e.rtl,
                    "mandatory": e.mandatory,
                }
                for e in entries
            ]
        )
        return 0

    header = f"{'code':<8}{'name':<24}{'script':<8}{'model_supported':<18}{'receipt_verified':<18}"
    print(header)
    print("-" * len(header))
    for e in sorted(entries, key=lambda e: (not e.mandatory, e.code)):
        print(
            f"{e.code:<8}{e.name:<24}{e.script:<8}{str(e.model_supported):<18}"
            f"{str(e.receipt_verified):<18}"
        )
    supported = sum(1 for e in entries if e.model_supported)
    verified = sum(1 for e in entries if e.receipt_verified)
    print(
        f"\n{supported}/{len(entries)} model_supported, "
        f"{verified}/{len(entries)} receipt_verified"
    )
    return 0


def cmd_models(args: argparse.Namespace) -> int:
    cache = CacheManager.from_env()
    cached_tess = cache.cached_tesseract_languages()
    tessdata_dir = cache.tessdata_dir()

    from receiptlingua.engines.tesseract_engine import TesseractEngine

    engine = TesseractEngine()
    system_langs = ()
    if engine.is_available():
        try:
            system_langs = tuple(engine._pt().get_languages(config=""))  # noqa: SLF001
        except Exception:  # noqa: BLE001
            system_langs = ()

    info = {
        "cache_dir": str(cache.cache_dir),
        "cache_dir_exists": cache.cache_dir.is_dir(),
        "tesseract": {
            "tessdata_dir": str(tessdata_dir),
            "cached_languages": list(cached_tess),
            "system_languages": list(system_langs),
        },
        "paddleocr_sidecar_configured": bool(
            __import__("os").environ.get(PADDLE_PYTHON_ENV_VAR)
        ),
    }
    if args.json:
        _print_json(info)
        return 0

    print(f"cache dir: {info['cache_dir']} (exists: {info['cache_dir_exists']})")
    print(f"tesseract tessdata dir: {tessdata_dir}")
    print(f"  cached (ours): {', '.join(cached_tess) or '(none)'}")
    print(f"  system (tesseract install): {', '.join(system_langs) or '(none)'}")
    all_mandatory = {e.code for e in load_matrix() if e.mandatory}
    installed = set(cached_tess) | set(system_langs)
    print(f"  missing (of {len(all_mandatory)} mandatory languages): "
          f"{len(all_mandatory) - len(installed & all_mandatory)} not installed")
    print(f"paddleocr sidecar configured: {info['paddleocr_sidecar_configured']}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    import os

    report: dict[str, Any] = {
        "os": platform.system(),
        "os_release": platform.release(),
        "arch": platform.machine(),
        "python_version": platform.python_version(),
    }

    caps = probe_capabilities()
    report["cpu_count"] = caps.cpu_count
    report["backends"] = [
        {"name": b.name, "available": b.available, "reason": b.reason} for b in caps.backends
    ]

    tesseract_bin = shutil.which("tesseract")
    report["tesseract_binary_found"] = tesseract_bin is not None
    report["tesseract_binary_path"] = tesseract_bin

    cache = CacheManager.from_env()
    report["cache_dir"] = str(cache.cache_dir)
    report["cache_dir_exists"] = cache.cache_dir.is_dir()
    report["cache_dir_tessdata_languages"] = list(cache.cached_tesseract_languages())

    # Never print the *value* of the sidecar env var (it's a filesystem
    # path a user might consider sensitive context, and more importantly
    # this rule generalizes to any future env var that might hold a
    # token) -- only whether it is set, and whether that interpreter
    # actually works.
    paddle_python = os.environ.get(PADDLE_PYTHON_ENV_VAR)
    report["paddle_sidecar_env_var_set"] = paddle_python is not None
    paddle_interpreter_ok = False
    if paddle_python:
        try:
            import subprocess

            proc = subprocess.run(
                [paddle_python, "-c", "import paddle, paddleocr"],
                capture_output=True,
                timeout=30,
                check=False,
            )
            paddle_interpreter_ok = proc.returncode == 0
        except (OSError, subprocess.SubprocessError):
            paddle_interpreter_ok = False
    report["paddle_sidecar_interpreter_working"] = paddle_interpreter_ok

    if args.json:
        _print_json(report)
        return 0

    print(f"OS: {report['os']} {report['os_release']} ({report['arch']})")
    print(f"Python: {report['python_version']}")
    print(f"CPU count: {report['cpu_count']}")
    print("Backends:")
    for b in report["backends"]:
        status = "available" if b["available"] else "NOT available"
        print(f"  {b['name']}: {status} ({b['reason']})")
    print(f"Tesseract binary: {'found at ' + tesseract_bin if tesseract_bin else 'NOT found'}")
    print(f"Cache dir: {report['cache_dir']} (exists: {report['cache_dir_exists']})")
    cached_langs = ", ".join(report["cache_dir_tessdata_languages"]) or "(none)"
    print(f"  cached tessdata languages: {cached_langs}")
    print(
        f"PaddleOCR sidecar env var ({PADDLE_PYTHON_ENV_VAR}) set: "
        f"{report['paddle_sidecar_env_var_set']}"
    )
    if paddle_python:
        print(f"  sidecar interpreter working: {paddle_interpreter_ok}")
    return 0


def cmd_cache_info(args: argparse.Namespace) -> int:
    cache = CacheManager.from_env()
    exists = cache.cache_dir.is_dir()
    total_bytes = 0
    file_count = 0
    if exists:
        for p in cache.cache_dir.rglob("*"):
            if p.is_file():
                total_bytes += p.stat().st_size
                file_count += 1

    info = {
        "cache_dir": str(cache.cache_dir),
        "exists": exists,
        "file_count": file_count,
        "total_bytes": total_bytes,
        "tessdata_languages": list(cache.cached_tesseract_languages()),
    }
    if args.json:
        _print_json(info)
        return 0

    print(f"cache dir: {info['cache_dir']} (exists: {exists})")
    print(f"files: {file_count}, total size: {total_bytes / 1024:.1f} KiB")
    print(f"tessdata languages: {', '.join(info['tessdata_languages']) or '(none)'}")
    return 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    print(
        "benchmark: not yet implemented, see docs/COMMIT_PLAN.md milestone 171-185 "
        "(datasets/benchmarking) -- this command intentionally does not fake results."
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="receiptlingua", description="Offline receipt OCR")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="Run OCR + field extraction on an image")
    p_scan.add_argument("path", type=str, help="Path to a receipt image")
    p_scan.add_argument("--json", action="store_true", help="Print the full JSON response")
    p_scan.add_argument(
        "--mode", choices=[m.value for m in Mode], default="auto", help="Processing mode"
    )
    p_scan.add_argument(
        "--lang",
        default="auto",
        help="Comma-separated language code(s), or 'auto' (engine default)",
    )
    p_scan.set_defaults(func=cmd_scan)

    p_langs = sub.add_parser("languages", help="Show the language capability matrix")
    p_langs.add_argument("--json", action="store_true")
    p_langs.set_defaults(func=cmd_languages)

    p_models = sub.add_parser("models", help="Show cached/installed OCR language data")
    p_models.add_argument("--json", action="store_true")
    p_models.set_defaults(func=cmd_models)

    p_doctor = sub.add_parser("doctor", help="Diagnose the local environment")
    p_doctor.add_argument("--json", action="store_true")
    p_doctor.set_defaults(func=cmd_doctor)

    p_bench = sub.add_parser("benchmark", help="(not yet implemented)")
    p_bench.set_defaults(func=cmd_benchmark)

    p_cache = sub.add_parser("cache", help="Cache directory operations")
    cache_sub = p_cache.add_subparsers(dest="cache_command", required=True)
    p_cache_info = cache_sub.add_parser("info", help="Show cache dir location/size/contents")
    p_cache_info.add_argument("--json", action="store_true")
    p_cache_info.set_defaults(func=cmd_cache_info)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

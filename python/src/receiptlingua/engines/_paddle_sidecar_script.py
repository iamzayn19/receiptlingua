"""Sidecar entry point run under a *separate* Python 3.11-3.13 interpreter.

This module is never imported by the main package's Python 3.14 process --
it is invoked as a subprocess via ``<sidecar-python> -m
receiptlingua.engines._paddle_sidecar_script`` (or by file path; the
module has no package-relative imports so either works) because
``paddlepaddle`` currently ships no build for Python 3.14 (see
docs/adr/0002-ocr-backend-selection.md). It talks to the parent process
over a tiny stdin/stdout JSON protocol:

Request (JSON on stdin, one line)::

    {"image_path": "/tmp/foo.png", "lang": "en"}

Response (JSON on stdout, one line)::

    {"ok": true, "engine_version": "3.7.0",
     "lines": [{"text": "...", "confidence": 0.99,
                "bbox": [x, y, w, h], "polygon": [[x,y], ...]}, ...]}

or on failure::

    {"ok": false, "error": "..."}

This is intentionally a stopgap, not the real sidecar transport described
as a future ADR item -- one request per process invocation, no model
caching across calls. It keeps the contract dead simple until the real
subprocess/IPC protocol layer is designed.
"""

from __future__ import annotations

import json
import sys


def _bbox_from_polygon(polygon: list[list[float]]) -> list[float]:
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)]


def main() -> int:
    request = json.loads(sys.stdin.readline())
    image_path = request["image_path"]
    lang = request.get("lang") or "en"

    try:
        import paddleocr  # noqa: PLC0415
        from paddleocr import PaddleOCR  # noqa: PLC0415

        ocr = PaddleOCR(
            lang=lang,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
        results = ocr.predict(image_path)

        lines = []
        for page in results:
            texts = page.get("rec_texts") or []
            scores = page.get("rec_scores") or []
            polys = page.get("rec_polys") or page.get("dt_polys") or []
            for i, text in enumerate(texts):
                if not text:
                    continue
                score = float(scores[i]) if i < len(scores) else 0.0
                entry = {"text": text, "confidence": score}
                if i < len(polys):
                    poly = polys[i]
                    poly_list = [[float(x), float(y)] for x, y in poly]
                    entry["polygon"] = poly_list
                    entry["bbox"] = _bbox_from_polygon(poly_list)
                else:
                    entry["bbox"] = [0.0, 0.0, 0.0, 0.0]
                lines.append(entry)

        response = {
            "ok": True,
            "engine_version": getattr(paddleocr, "__version__", "unknown"),
            "lines": lines,
        }
    except Exception as exc:  # noqa: BLE001 -- reported to parent, not raised here
        response = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    sys.stdout.write(json.dumps(response))
    sys.stdout.write("\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

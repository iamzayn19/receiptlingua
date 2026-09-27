"""Long-lived sidecar daemon run under a *separate* Python 3.11-3.13 interpreter.

Replaces the old one-shot ``_paddle_sidecar_script.py`` (removed). This
module is never imported by the main package's Python 3.14 process -- it
is spawned once as a persistent child process via ``<sidecar-python> -m
receiptlingua.engines._paddle_sidecar_daemon`` (or by file path; the
module has no package-relative imports so either works), because
``paddlepaddle`` currently ships no build for Python 3.14 (see
docs/adr/0002-ocr-backend-selection.md).

Transport (see docs/adr/0003-sidecar-transport.md for the full rationale):
newline-delimited JSON over the daemon's stdin/stdout. The parent process
keeps this daemon alive across many ``recognize()`` calls instead of
spawning a fresh interpreter (and re-loading PaddleOCR's models) per call.

Request (JSON on stdin, one line per request)::

    {"id": 1, "image_path": "/tmp/foo.png", "lang": "en"}

Response (JSON on stdout, one line per response)::

    {"id": 1, "ok": true, "engine_version": "3.7.0",
     "lines": [{"text": "...", "confidence": 0.99,
                "bbox": [x, y, w, h], "polygon": [[x,y], ...]}, ...]}

or on a per-request failure (the daemon itself keeps running)::

    {"id": 1, "ok": false, "error": "..."}

Shutdown: send ``{"cmd": "shutdown"}`` on stdin, or simply close stdin
(EOF) or send SIGTERM -- all three cleanly stop the loop and exit 0. The
parent (``PaddleOCREngine``) uses "close stdin, then wait with a
timeout, then terminate" as its shutdown sequence; see that module.

Concurrency: this is a deliberately simple v1 -- a single-threaded FIFO
loop that fully processes one request (including writing its response)
before reading the next line from stdin. There is no concurrent/batched
request handling. This is an honest scope choice, not an oversight: the
underlying PaddleOCR ``predict()`` call is CPU-bound per process anyway,
and a FIFO loop is enough to eliminate the actual cost this change
targets (repeated interpreter startup + model load), without taking on
the complexity of a request-multiplexing protocol in the same pass.

Models are cached per language for the lifetime of this process (a
dict keyed by ``lang``), so the *first* request for a given language
pays PaddleOCR's model-load cost and every subsequent request for that
same language reuses the already-loaded model.
"""

from __future__ import annotations

import json
import sys

_ocr_instances: dict[str, object] = {}


def _bbox_from_polygon(polygon: list[list[float]]) -> list[float]:
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)]


def _get_ocr(lang: str):
    ocr = _ocr_instances.get(lang)
    if ocr is None:
        from paddleocr import PaddleOCR  # noqa: PLC0415

        ocr = PaddleOCR(
            lang=lang,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
        _ocr_instances[lang] = ocr
    return ocr


def _handle_request(request: dict) -> dict:
    request_id = request.get("id")
    try:
        image_path = request["image_path"]
        lang = request.get("lang") or "en"

        import paddleocr  # noqa: PLC0415

        ocr = _get_ocr(lang)
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

        return {
            "id": request_id,
            "ok": True,
            "engine_version": getattr(paddleocr, "__version__", "unknown"),
            "lines": lines,
        }
    except Exception as exc:  # noqa: BLE001 -- reported to parent, daemon must survive
        return {
            "id": request_id,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


def main() -> int:
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            bad_request = {"id": None, "ok": False, "error": f"bad request JSON: {exc}"}
            sys.stdout.write(json.dumps(bad_request))
            sys.stdout.write("\n")
            sys.stdout.flush()
            continue

        if request.get("cmd") == "shutdown":
            break

        response = _handle_request(request)
        sys.stdout.write(json.dumps(response))
        sys.stdout.write("\n")
        sys.stdout.flush()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

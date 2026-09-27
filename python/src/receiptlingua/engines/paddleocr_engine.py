"""PaddleOCR backend adapter.

`paddlepaddle` currently ships no build for this package's own Python
(3.14 on this machine -- see docs/adr/0002-ocr-backend-selection.md), so
this backend cannot be imported in-process. Instead it runs as a
**subprocess sidecar**: a separate Python 3.11-3.13 interpreter with
`paddlepaddle`/`paddleocr` installed, pointed at via the
``RECEIPTLINGUA_PADDLE_PYTHON`` environment variable, running
``receiptlingua.engines._paddle_sidecar_script`` and talking over a
one-shot JSON stdin/stdout protocol (see that module's docstring for the
exact wire format).

This is a stopgap, not the final sidecar transport -- there is no model
caching across calls (each `recognize()` call pays PaddleOCR's model-load
cost fresh), and the protocol is deliberately the simplest thing that
works: one request, one response, one process per image. The real
multi-request sidecar protocol is still an open ADR item.

If ``RECEIPTLINGUA_PADDLE_PYTHON`` is unset or does not point at a usable
interpreter, ``is_available()`` returns False and ``recognize()`` raises
``UnsupportedBackendError`` -- never a crash.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from receiptlingua.engines.base import OCREngine
from receiptlingua.engines.errors import OCRFailedError, UnsupportedBackendError
from receiptlingua.engines.types import BBox, EngineResult, EngineTextLine

#: Environment variable pointing at the sidecar Python interpreter
#: (Python 3.11-3.13, with paddlepaddle + paddleocr installed) that
#: actually runs PaddleOCR. Mirrors the RECEIPTLINGUA_CACHE_DIR naming
#: convention used elsewhere in this package.
PADDLE_PYTHON_ENV_VAR = "RECEIPTLINGUA_PADDLE_PYTHON"

# PaddleOCR (PP-OCRv5) language groups actually smoke-tested against this
# package's fixtures -- see docs/adr/0002-ocr-backend-selection.md for
# real recognized-text/confidence results per language. Kept intentionally
# short (not PaddleOCR's full advertised language list) since only these
# have been verified against real, rendered, non-placeholder text.
_VERIFIED_LANGUAGES: tuple[str, ...] = ("en", "ta", "ar")

_SUBPROCESS_TIMEOUT_SECONDS = 120


class PaddleOCREngine(OCREngine):
    name = "paddleocr"

    def __init__(self, sidecar_python: str | None = None):
        self._sidecar_python = sidecar_python or os.environ.get(PADDLE_PYTHON_ENV_VAR)

    def is_available(self) -> bool:
        if not self._sidecar_python:
            return False
        return Path(self._sidecar_python).is_file() and os.access(self._sidecar_python, os.X_OK)

    def supported_languages(self) -> tuple[str, ...]:
        if not self.is_available():
            return ()
        return _VERIFIED_LANGUAGES

    def recognize(
        self,
        image: np.ndarray,
        *,
        languages: tuple[str, ...] = (),
    ) -> EngineResult:
        if not self.is_available():
            raise UnsupportedBackendError(
                self.name,
                f"{PADDLE_PYTHON_ENV_VAR} is not set or does not point at a usable Python "
                "interpreter -- see docs/adr/0002-ocr-backend-selection.md for how to set up "
                "the PaddleOCR sidecar venv",
            )

        lang = languages[0] if languages else "en"

        from PIL import Image as PILImage

        script_path = Path(__file__).parent / "_paddle_sidecar_script.py"

        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "input.png"
            PILImage.fromarray(image).save(image_path)

            request = json.dumps({"image_path": str(image_path), "lang": lang}) + "\n"

            try:
                proc = subprocess.run(  # noqa: S603 -- fixed argv, no shell, trusted sidecar path
                    [self._sidecar_python, str(script_path)],
                    input=request,
                    capture_output=True,
                    text=True,
                    timeout=_SUBPROCESS_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired as exc:
                raise OCRFailedError(self.name, f"sidecar process timed out: {exc}") from exc
            except OSError as exc:
                raise OCRFailedError(self.name, f"failed to launch sidecar process: {exc}") from exc

            if proc.returncode != 0:
                raise OCRFailedError(
                    self.name,
                    f"sidecar process exited {proc.returncode}: {proc.stderr.strip()[-2000:]}",
                )

            stdout = proc.stdout.strip().splitlines()
            if not stdout:
                raise OCRFailedError(
                    self.name, f"sidecar produced no output; stderr: {proc.stderr.strip()[-2000:]}"
                )

            try:
                response = json.loads(stdout[-1])
            except json.JSONDecodeError as exc:
                raise OCRFailedError(self.name, f"sidecar returned malformed JSON: {exc}") from exc

        if not response.get("ok"):
            raise OCRFailedError(self.name, response.get("error", "unknown sidecar error"))

        text_lines = []
        for entry in response.get("lines", []):
            x, y, w, h = entry["bbox"]
            polygon = None
            if entry.get("polygon"):
                polygon = tuple((p[0], p[1]) for p in entry["polygon"])
            confidence = float(entry["confidence"])
            status = "ok" if confidence >= 0.4 else "uncertain"
            text_lines.append(
                EngineTextLine(
                    text=entry["text"],
                    bbox=BBox(x, y, w, h),
                    confidence=confidence,
                    status=status,
                    polygon=polygon,
                    language=lang,
                )
            )

        warnings: tuple[str, ...] = () if text_lines else ("no text detected",)

        return EngineResult(
            engine=self.name,
            engine_version=response.get("engine_version", "unknown"),
            text_lines=tuple(text_lines),
            warnings=warnings,
        )

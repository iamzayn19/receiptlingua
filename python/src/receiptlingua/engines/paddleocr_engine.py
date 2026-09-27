"""PaddleOCR backend adapter.

`paddlepaddle` currently ships no build for this package's own Python
(3.14 on this machine -- see docs/adr/0002-ocr-backend-selection.md), so
this backend cannot be imported in-process. Instead it runs as a
**persistent subprocess sidecar daemon**: a separate Python 3.11-3.13
interpreter with `paddlepaddle`/`paddleocr` installed, pointed at via the
``RECEIPTLINGUA_PADDLE_PYTHON`` environment variable, running
``receiptlingua.engines._paddle_sidecar_daemon`` and talking over
newline-delimited JSON on stdin/stdout (see
docs/adr/0003-sidecar-transport.md for the transport decision and that
module's docstring for the exact wire format).

Unlike the earlier one-process-per-call stopgap, ``PaddleOCREngine`` now
spawns the daemon **lazily on first use** and keeps it alive across every
subsequent ``recognize()`` call on the same engine instance -- the
PaddleOCR model is loaded once, not once per call. Use ``close()`` (or
the engine as a context manager) to shut the daemon down explicitly, e.g.
at the end of a batch job or CLI invocation.

If ``RECEIPTLINGUA_PADDLE_PYTHON`` is unset or does not point at a usable
interpreter, ``is_available()`` returns False and ``recognize()`` raises
``UnsupportedBackendError`` -- never a crash.
"""

from __future__ import annotations

import json
import os
import selectors
import subprocess
import tempfile
import threading
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

#: Timeout for a single request/response round trip with the daemon. This
#: covers the (much slower) first request for a given language, since
#: that's the one that pays PaddleOCR's model-load cost; warm requests
#: return far sooner in practice.
_REQUEST_TIMEOUT_SECONDS = 120

#: Timeout for the daemon to exit cleanly after a shutdown request before
#: it is forcibly terminated.
_SHUTDOWN_TIMEOUT_SECONDS = 10


class PaddleOCREngine(OCREngine):
    """PaddleOCR adapter that owns one persistent sidecar daemon.

    One ``PaddleOCREngine`` instance == at most one live daemon
    subprocess, spawned lazily on the first ``recognize()`` call and
    reused for every call after that. Not safe to call ``recognize()``
    concurrently from multiple threads on the same instance (the daemon
    itself is single-request-at-a-time; see
    ``_paddle_sidecar_daemon.py``'s docstring) -- a lock serializes calls
    so concurrent callers are correct but not concurrent.
    """

    name = "paddleocr"

    def __init__(self, sidecar_python: str | None = None):
        self._sidecar_python = sidecar_python or os.environ.get(PADDLE_PYTHON_ENV_VAR)
        self._proc: subprocess.Popen | None = None
        self._next_id = 0
        self._lock = threading.Lock()

    def is_available(self) -> bool:
        if not self._sidecar_python:
            return False
        return Path(self._sidecar_python).is_file() and os.access(self._sidecar_python, os.X_OK)

    def supported_languages(self) -> tuple[str, ...]:
        if not self.is_available():
            return ()
        return _VERIFIED_LANGUAGES

    # -- daemon lifecycle -------------------------------------------------

    def _daemon_module_path(self) -> Path:
        return Path(__file__).parent / "_paddle_sidecar_daemon.py"

    def _is_daemon_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def _ensure_daemon(self) -> subprocess.Popen:
        if self._is_daemon_alive():
            return self._proc  # type: ignore[return-value]

        assert self._sidecar_python is not None
        try:
            self._proc = subprocess.Popen(  # noqa: S603 -- fixed argv, no shell, trusted sidecar path
                [self._sidecar_python, str(self._daemon_module_path())],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            raise OCRFailedError(self.name, f"failed to launch sidecar daemon: {exc}") from exc
        self._next_id = 0
        return self._proc

    def close(self) -> None:
        """Shut down the sidecar daemon, if one is running.

        Sends a ``{"cmd": "shutdown"}`` message, closes stdin, and waits
        up to ``_SHUTDOWN_TIMEOUT_SECONDS`` for the process to exit before
        forcibly terminating (and, failing that, killing) it -- so a
        hung or unresponsive daemon can never become a leaked/zombie
        process.
        """
        proc = self._proc
        if proc is None:
            return
        self._proc = None

        if proc.poll() is not None:
            return  # already exited

        try:
            if proc.stdin and not proc.stdin.closed:
                try:
                    proc.stdin.write(json.dumps({"cmd": "shutdown"}) + "\n")
                    proc.stdin.flush()
                except (BrokenPipeError, OSError):
                    pass
                try:
                    proc.stdin.close()
                except OSError:
                    pass
            proc.wait(timeout=_SHUTDOWN_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=_SHUTDOWN_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=_SHUTDOWN_TIMEOUT_SECONDS)
        finally:
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()

    def __enter__(self) -> PaddleOCREngine:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:  # noqa: BLE001 -- __del__ must never raise
            pass

    # -- request/response --------------------------------------------------

    def _send_request(self, proc: subprocess.Popen, request: dict) -> dict:
        assert proc.stdin is not None
        assert proc.stdout is not None

        try:
            proc.stdin.write(json.dumps(request) + "\n")
            proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            self._proc = None
            raise OCRFailedError(
                self.name, f"sidecar daemon pipe broke while sending request: {exc}"
            ) from exc

        sel = selectors.DefaultSelector()
        try:
            sel.register(proc.stdout, selectors.EVENT_READ)
            events = sel.select(timeout=_REQUEST_TIMEOUT_SECONDS)
        finally:
            sel.close()

        if not events:
            # Daemon is hung or dead-but-not-reaped; treat it as unusable
            # so the next call spawns a fresh one rather than hanging.
            self.close()
            raise OCRFailedError(
                self.name,
                f"sidecar daemon did not respond within {_REQUEST_TIMEOUT_SECONDS}s",
            )

        line = proc.stdout.readline()
        if not line:
            stderr_tail = ""
            if proc.stderr:
                try:
                    stderr_tail = proc.stderr.read()[-2000:]
                except Exception:  # noqa: BLE001
                    stderr_tail = ""
            self.close()
            raise OCRFailedError(
                self.name,
                f"sidecar daemon closed its output unexpectedly (crashed?); stderr: {stderr_tail}",
            )

        try:
            return json.loads(line)
        except json.JSONDecodeError as exc:
            raise OCRFailedError(
                self.name, f"sidecar daemon returned malformed JSON: {exc}"
            ) from exc

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

        with self._lock:
            proc = self._ensure_daemon()

            with tempfile.TemporaryDirectory() as tmpdir:
                image_path = Path(tmpdir) / "input.png"
                PILImage.fromarray(image).save(image_path)

                self._next_id += 1
                request = {"id": self._next_id, "image_path": str(image_path), "lang": lang}
                response = self._send_request(proc, request)

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

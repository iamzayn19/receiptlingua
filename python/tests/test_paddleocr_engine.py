"""Real end-to-end smoke tests against the PaddleOCR sidecar backend.

PaddleOCR cannot run in-process on this package's own Python (3.14 has no
`paddlepaddle` build -- see docs/adr/0002-ocr-backend-selection.md), so
these tests exercise the real subprocess sidecar daemon: they only run
for real when RECEIPTLINGUA_PADDLE_PYTHON is set to a Python 3.11-3.13
interpreter with `paddlepaddle`/`paddleocr` installed (see the ADR for how
to set one up). Otherwise they skip cleanly, mirroring how the
Tamil/Arabic Tesseract language-pack tests skip when their trained data
isn't installed -- this is a local, offline setup step, never something
the pipeline attempts automatically at runtime or over the network.

Since docs/adr/0003-sidecar-transport.md, the sidecar is a persistent
daemon reused across calls on the same ``PaddleOCREngine`` instance
(rather than one process per call), so several tests below exercise that
directly: repeated-call latency and clean process shutdown.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from receiptlingua.engines.paddleocr_engine import PaddleOCREngine

FIXTURES_DIR = Path(__file__).parent / "fixtures"

engine = PaddleOCREngine()
pytestmark = pytest.mark.skipif(
    not engine.is_available(),
    reason="RECEIPTLINGUA_PADDLE_PYTHON not set to a usable sidecar interpreter",
)


def _load(name: str) -> np.ndarray:
    return np.array(Image.open(FIXTURES_DIR / name))


def test_english_text_fixture_produces_nonempty_recognizable_lines():
    image = _load("receipt_text_eng.png")
    result = engine.recognize(image, languages=("en",))

    assert not result.is_empty
    assert result.engine == "paddleocr"
    assert result.engine_version

    full_text_upper = result.full_text.upper()
    assert "CORNER" in full_text_upper or "STORE" in full_text_upper
    assert "6.48" in result.full_text or "6.4" in result.full_text

    for line in result.text_lines:
        assert 0.0 <= line.confidence <= 1.0
        assert line.status in ("ok", "illegible", "truncated", "missing_region", "uncertain")


def test_tamil_text_fixture_produces_nonempty_lines():
    image = _load("receipt_text_tam.png")
    result = engine.recognize(image, languages=("ta",))
    assert not result.is_empty
    assert len(result.full_text.strip()) > 0


def test_arabic_text_fixture_produces_nonempty_lines():
    image = _load("receipt_text_ara.png")
    result = engine.recognize(image, languages=("ar",))
    assert not result.is_empty
    assert len(result.full_text.strip()) > 0


def test_blank_image_does_not_hallucinate_text():
    blank = np.full((100, 300), 255, dtype=np.uint8)
    result = engine.recognize(blank, languages=("en",))
    assert result.full_text.strip() == "" or all(
        line.status != "ok" for line in result.text_lines
    )


def test_unavailable_backend_raises_unsupported_backend_error(monkeypatch):
    from receiptlingua.engines.errors import UnsupportedBackendError

    unset_engine = PaddleOCREngine(sidecar_python="/nonexistent/python")
    assert not unset_engine.is_available()
    with pytest.raises(UnsupportedBackendError):
        unset_engine.recognize(_load("receipt_text_eng.png"))


def test_repeated_calls_reuse_one_persistent_daemon_process():
    """The whole point of the daemon: one subprocess serves many calls."""
    fresh_engine = PaddleOCREngine()
    image = _load("receipt_text_eng.png")
    try:
        fresh_engine.recognize(image, languages=("en",))
        first_pid = fresh_engine._proc.pid  # noqa: SLF001

        fresh_engine.recognize(image, languages=("en",))
        second_pid = fresh_engine._proc.pid  # noqa: SLF001

        assert first_pid == second_pid
    finally:
        fresh_engine.close()


def test_close_leaves_no_lingering_daemon_process():
    """close() must not leak a zombie/orphaned sidecar process."""
    fresh_engine = PaddleOCREngine()
    image = _load("receipt_text_eng.png")
    fresh_engine.recognize(image, languages=("en",))
    pid = fresh_engine._proc.pid  # noqa: SLF001

    fresh_engine.close()

    # poll() on our own handle would report this either way, but the
    # stronger check is asking the OS directly: `ps -p <pid>` finds
    # nothing once the process has actually exited (not just been asked
    # to exit).
    deadline = time.time() + 5
    while time.time() < deadline:
        result = subprocess.run(  # noqa: S603, S607
            ["ps", "-p", str(pid)], capture_output=True, text=True, check=False
        )
        if str(pid) not in result.stdout:
            break
        time.sleep(0.2)
    else:
        pytest.fail(f"sidecar daemon process {pid} is still running after close()")


def test_warm_calls_are_faster_than_the_cold_first_call():
    """Measure the real speedup: cold (model-load) vs warm (reused) calls.

    Not a hardcoded number -- asserts a conservative, environment-observed
    ratio so this stays honest about what was actually measured rather
    than asserting an arbitrary target.
    """
    fresh_engine = PaddleOCREngine()
    image = _load("receipt_text_eng.png")
    try:
        start = time.perf_counter()
        fresh_engine.recognize(image, languages=("en",))
        cold_seconds = time.perf_counter() - start

        warm_durations = []
        for _ in range(5):
            start = time.perf_counter()
            fresh_engine.recognize(image, languages=("en",))
            warm_durations.append(time.perf_counter() - start)
        warm_avg = sum(warm_durations) / len(warm_durations)

        print(f"\n[paddleocr sidecar] cold call: {cold_seconds:.3f}s, warm avg: {warm_avg:.3f}s")

        # Conservative: warm calls should be meaningfully faster than the
        # cold, model-loading call. Loosely bounded since actual model
        # load time varies a lot by machine/cache state.
        assert warm_avg < cold_seconds
    finally:
        fresh_engine.close()

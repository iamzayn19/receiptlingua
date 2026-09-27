"""Tesseract OCR backend adapter.

The default, real, working backend in this environment (see
docs/adr/0002-ocr-backend-selection.md for why PaddleOCR could not be
validated on Python 3.14). Tesseract is Apache-2.0, ships wide language
data coverage via ``.traineddata`` packs, and is CPU-only -- no GPU
capability probing is needed for it.
"""

from __future__ import annotations

import importlib.util
import shutil

import numpy as np

from receiptlingua.engines.base import OCREngine
from receiptlingua.engines.cache import CacheManager
from receiptlingua.engines.errors import OCRFailedError, UnsupportedBackendError
from receiptlingua.engines.types import BBox, EngineResult, EngineTextLine, EngineWord

# Tesseract confidence is reported on a 0-100 scale (or -1 for "no
# confidence"/non-text); the protocol schema wants 0-1.
_CONF_SCALE = 100.0

# Below this Tesseract confidence, a line is reported as "uncertain"
# rather than "ok" -- never silently upgraded to a confident result.
_UNCERTAIN_CONFIDENCE_THRESHOLD = 0.4


class TesseractEngine(OCREngine):
    name = "tesseract"

    def __init__(self, cache: CacheManager | None = None):
        self._cache = cache or CacheManager.from_env()
        self._pytesseract = None  # lazily imported so import cost is paid once, on demand

    def is_available(self) -> bool:
        if shutil.which("tesseract") is None:
            return False
        return importlib.util.find_spec("pytesseract") is not None

    def _pt(self):
        if self._pytesseract is None:
            if not self.is_available():
                raise UnsupportedBackendError(
                    self.name, "tesseract binary or pytesseract package not found"
                )
            import pytesseract  # noqa: PLC0415 -- intentional lazy import

            self._pytesseract = pytesseract
        return self._pytesseract

    def _system_tessdata_dirs(self) -> tuple[str, ...]:
        """Best-effort discovery of the system Tesseract's own tessdata dir.

        Used only to *check* language availability locally (never to
        download); ``TESSDATA_PREFIX``, when set, takes priority.
        """
        import os

        dirs = []
        prefix = os.environ.get("TESSDATA_PREFIX")
        if prefix:
            dirs.append(prefix)
        # Common Homebrew location on Apple Silicon/macOS.
        dirs.append("/opt/homebrew/share/tessdata")
        dirs.append("/usr/share/tesseract-ocr/tessdata")
        dirs.append("/usr/local/share/tessdata")
        return tuple(dirs)

    def supported_languages(self) -> tuple[str, ...]:
        if not self.is_available():
            return ()
        try:
            langs = tuple(self._pt().get_languages(config=""))
        except Exception:
            langs = ()
        cached = self._cache.cached_tesseract_languages()
        return tuple(sorted(set(langs) | set(cached)))

    def recognize(
        self,
        image: np.ndarray,
        *,
        languages: tuple[str, ...] = (),
    ) -> EngineResult:
        if not self.is_available():
            raise UnsupportedBackendError(self.name, "tesseract binary or pytesseract not found")

        pt = self._pt()
        lang_arg = "+".join(languages) if languages else "eng"

        from PIL import Image as PILImage

        pil_image = PILImage.fromarray(image)

        try:
            data = pt.image_to_data(
                pil_image, lang=lang_arg, output_type=pt.Output.DICT
            )
            version = str(pt.get_tesseract_version())
        except pt.TesseractError as exc:
            raise OCRFailedError(self.name, str(exc)) from exc
        except Exception as exc:  # pragma: no cover - defensive
            raise OCRFailedError(self.name, f"unexpected failure: {exc}") from exc

        text_lines = _group_into_lines(data)
        warnings: list[str] = []
        if not text_lines:
            warnings.append("no text detected")

        return EngineResult(
            engine=self.name,
            engine_version=version,
            text_lines=tuple(text_lines),
            warnings=tuple(warnings),
        )


def _group_into_lines(data: dict) -> list[EngineTextLine]:
    """Group pytesseract's flat word-level TSV-style dict into text lines.

    ``data`` follows ``pytesseract.image_to_data`` output_type=DICT shape:
    parallel lists keyed by ``level``/``page_num``/``block_num``/
    ``par_num``/``line_num``/``word_num``/``left``/``top``/``width``/
    ``height``/``conf``/``text``.
    """
    n = len(data.get("text", []))
    lines_by_key: dict[tuple[int, int, int], list[int]] = {}
    for i in range(n):
        text = data["text"][i].strip()
        if not text:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines_by_key.setdefault(key, []).append(i)

    result: list[EngineTextLine] = []
    for key in sorted(lines_by_key):
        indices = lines_by_key[key]
        words: list[EngineWord] = []
        xs0, ys0, xs1, ys1 = [], [], [], []
        confs = []
        for i in indices:
            text = data["text"][i].strip()
            x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            raw_conf = data["conf"][i]
            conf = max(float(raw_conf), 0.0) / _CONF_SCALE if raw_conf not in (-1, "-1") else 0.0
            status = "ok" if conf >= _UNCERTAIN_CONFIDENCE_THRESHOLD else "uncertain"
            words.append(
                EngineWord(text=text, bbox=BBox(x, y, w, h), confidence=conf, status=status)
            )
            xs0.append(x)
            ys0.append(y)
            xs1.append(x + w)
            ys1.append(y + h)
            confs.append(conf)

        if not words:
            continue

        line_bbox = BBox(
            x=min(xs0), y=min(ys0), width=max(xs1) - min(xs0), height=max(ys1) - min(ys0)
        )
        line_conf = sum(confs) / len(confs)
        line_status = "ok" if line_conf >= _UNCERTAIN_CONFIDENCE_THRESHOLD else "uncertain"
        result.append(
            EngineTextLine(
                text=" ".join(w.text for w in words),
                bbox=line_bbox,
                confidence=line_conf,
                status=line_status,
                words=tuple(words),
            )
        )
    return result

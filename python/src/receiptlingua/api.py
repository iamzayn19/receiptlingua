"""Public Python API: ``ReceiptOCR``.

This is the first place all prior milestones (preprocessing, OCR engines,
language/script identification, structured field extraction) are wired
together into one real, callable pipeline, producing output that matches
``protocol/schema/response.schema.json`` exactly.

Usage::

    from receiptlingua import ReceiptOCR

    ocr = ReceiptOCR()  # optionally: mode="auto", cache_dir=..., backend=...
    result = ocr.scan("receipt.jpg")
    print(result.full_text)
    print(result.to_json())
"""

from __future__ import annotations

import io
import json
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from receiptlingua.engines import registry
from receiptlingua.engines.base import OCREngine
from receiptlingua.engines.cache import CacheManager
from receiptlingua.engines.errors import EngineError
from receiptlingua.engines.mode import should_escalate
from receiptlingua.engines.types import EngineResult, EngineTextLine
from receiptlingua.extract.extractor import extract_fields
from receiptlingua.langid.tagging import tag_document
from receiptlingua.pipeline.preprocess.exif_orientation import (
    apply_orientation,
    read_exif_orientation,
)
from receiptlingua.pipeline.preprocess.loading import (
    ERR_UNSUPPORTED_FORMAT,
    LoadResult,
    load_image,
)
from receiptlingua.pipeline.preprocess.orchestrator import Mode, preprocess_array

#: Protocol schema_version this module's output conforms to. See
#: protocol/VERSIONING.md -- bump only alongside a matching schema change.
SCHEMA_VERSION = "0.1.0"

#: ISO 15924 script codes whose natural reading direction is right-to-left.
#: Used to derive the ``rtl_flags`` that ``extract_fields``/reading-order
#: reconstruction need, from the langid module's per-line script tags.
_RTL_SCRIPTS = frozenset({"Arab", "Hebr", "Thaa"})


class ReceiptOCRError(Exception):
    """Base class for public API errors. Carries the same ``code`` vocabulary
    as ``protocol/schema/error.schema.json`` so callers can branch on
    ``error.code`` without inspecting ``message`` text."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            error["details"] = self.details
        return {"schema_version": SCHEMA_VERSION, "error": error}


class InvalidImageError(ReceiptOCRError):
    def __init__(self, reason: str, details: dict[str, Any] | None = None):
        super().__init__("INVALID_IMAGE", f"Invalid image: {reason}", details)


class UnsupportedFormatError(ReceiptOCRError):
    def __init__(self, reason: str, details: dict[str, Any] | None = None):
        super().__init__("UNSUPPORTED_FORMAT", f"Unsupported image format: {reason}", details)


class InvalidConfigurationError(ReceiptOCRError):
    def __init__(self, reason: str, details: dict[str, Any] | None = None):
        super().__init__("INVALID_CONFIGURATION", reason, details)


# Loader error codes (loading.py's ERR_* constants) that mean "wrong kind of
# file" rather than "this looked like an image but was corrupt/too big".
_UNSUPPORTED_FORMAT_ERRORS = frozenset({ERR_UNSUPPORTED_FORMAT})


def _wrap_load_error(load_result: LoadResult) -> ReceiptOCRError:
    assert load_result.error is not None
    details = {"reason": load_result.error}
    if load_result.error in _UNSUPPORTED_FORMAT_ERRORS:
        return UnsupportedFormatError(load_result.error, details)
    return InvalidImageError(load_result.error, details)


def _engine_error_to_public(exc: EngineError) -> ReceiptOCRError:
    return ReceiptOCRError(exc.code, exc.message, exc.details)


@dataclass(frozen=True)
class ReceiptResult:
    """A single scan's result, matching ``response.schema.json`` exactly.

    Supports both attribute access (``result.full_text``,
    ``result.fields``) and ``.to_dict()``/``.to_json()`` for the exact
    schema-shaped payload (which uses the schema's own snake_case keys,
    e.g. ``engine_version``, ``processing_time_ms``).
    """

    schema_version: str
    engine: str
    engine_version: str
    mode: str
    image: dict[str, Any]
    processing_time_ms: float
    languages: list[dict[str, Any]]
    scripts: list[str]
    full_text: str
    text_lines: list[dict[str, Any]]
    warnings: list[str]
    fields: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "engine": self.engine,
            "engine_version": self.engine_version,
            "mode": self.mode,
            "image": self.image,
            "processing_time_ms": self.processing_time_ms,
            "languages": self.languages,
            "scripts": self.scripts,
            "full_text": self.full_text,
            "text_lines": self.text_lines,
            "warnings": self.warnings,
            "fields": self.fields,
        }

    def to_json(self, **kwargs: Any) -> str:
        kwargs.setdefault("ensure_ascii", False)
        kwargs.setdefault("indent", 2)
        return json.dumps(self.to_dict(), **kwargs)


def _load_pixels(image: Any) -> tuple[np.ndarray, str | None, LoadResult | None]:
    """Normalize ``scan()``'s accepted input types down to a decoded array.

    Returns ``(array, source_path_or_None, load_result_or_None)``.
    ``load_result`` (with width/height/format) is only available when the
    input was a real file path, since that is the only case
    ``pipeline.preprocess.loading.load_image`` (with its decompression-bomb
    and format guards) can run its file-level checks against.
    """
    if isinstance(image, (str, Path)):
        path = str(image)
        result = load_image(path)
        if not result.ok:
            raise _wrap_load_error(result)
        return result.image, path, result

    if isinstance(image, np.ndarray):
        return image, None, None

    if isinstance(image, Image.Image):
        return np.asarray(image.convert("RGB")), None, None

    if isinstance(image, bytes):
        # Round-trip through a temp file so the same defensive
        # loading/validation path (size limits, decompression-bomb guard,
        # format allowlist) runs for in-memory bytes too.
        try:
            with Image.open(io.BytesIO(image)) as probe:
                suffix = f".{(probe.format or 'png').lower()}"
        except Exception:  # noqa: BLE001 - untrusted bytes must never crash us
            suffix = ".bin"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(image)
            tmp_path = tmp.name
        try:
            result = load_image(tmp_path)
            if not result.ok:
                raise _wrap_load_error(result)
            return result.image, None, result
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    raise InvalidConfigurationError(
        f"unsupported input type for scan(): {type(image).__name__}; "
        "expected a file path, bytes, PIL.Image.Image, or numpy.ndarray"
    )


class ReceiptOCR:
    """The public, end-to-end receipt OCR API.

    Wires together preprocessing -> OCR engine -> language/script tagging
    -> structured field extraction into one call, ``scan()``.
    """

    def __init__(
        self,
        *,
        mode: str = "auto",
        cache_dir: str | Path | None = None,
        backend: str | None = None,
        languages: tuple[str, ...] | list[str] | None = None,
    ):
        try:
            self.mode = Mode(mode)
        except ValueError as exc:
            raise InvalidConfigurationError(
                f"invalid mode '{mode}': expected one of fast/accurate/auto"
            ) from exc

        self._cache = (
            CacheManager(cache_dir=Path(cache_dir).expanduser())
            if cache_dir is not None
            else CacheManager.from_env()
        )
        self._backend_name = backend
        self._engine: OCREngine | None = None
        # "auto"/None means let the engine use its own default language
        # (e.g. Tesseract's "eng"); an explicit list is passed straight
        # through to OCREngine.recognize(languages=...), so multilingual
        # recognition only actually engages the right traineddata/model
        # when the caller names the language(s) -- this pipeline does not
        # (yet) run a language-ID pre-pass to pick languages automatically,
        # since that would need a first OCR pass in some default language
        # to even have text to identify. Documented, not hidden.
        self.languages: tuple[str, ...] = tuple(languages) if languages else ()

    def _resolve_engine(self) -> OCREngine:
        if self._engine is not None:
            return self._engine
        try:
            engine = (
                registry.get_engine(self._backend_name)
                if self._backend_name
                else registry.get_default_engine()
            )
        except EngineError as exc:
            raise _engine_error_to_public(exc) from exc
        if self._backend_name and not engine.is_available():
            raise _engine_error_to_public(
                EngineError(
                    "UNSUPPORTED_BACKEND",
                    f"Backend '{self._backend_name}' is not available in this environment",
                )
            )
        self._engine = engine
        return engine

    def _run_ocr(self, engine: OCREngine, pixels: np.ndarray) -> EngineResult:
        try:
            return engine.recognize(pixels, languages=self.languages)
        except EngineError as exc:
            raise _engine_error_to_public(exc) from exc

    def scan(self, image: Any) -> ReceiptResult:
        """Run the full pipeline on one image and return a schema-shaped result.

        ``image`` may be a file path (``str``/``Path``), raw ``bytes``, a
        ``PIL.Image.Image``, or an already-decoded RGB ``numpy.ndarray``.
        """
        start = time.perf_counter()

        pixels, source_path, load_result = _load_pixels(image)

        exif_orientation = read_exif_orientation(source_path) if source_path else 1
        working = apply_orientation(pixels, exif_orientation)

        preprocessed = preprocess_array(working, mode=self.mode, exif_orientation=1)

        engine = self._resolve_engine()
        first_pass = self._run_ocr(engine, preprocessed.image)

        warnings = list(first_pass.warnings)
        final_result = first_pass

        if should_escalate(self.mode, first_pass) and self.mode == Mode.AUTO:
            escalated = preprocess_array(working, mode=Mode.ACCURATE, exif_orientation=1)
            second_pass = self._run_ocr(engine, escalated.image)
            if not second_pass.is_empty and (
                first_pass.is_empty or len(second_pass.text_lines) >= len(first_pass.text_lines)
            ):
                final_result = second_pass
                warnings = list(second_pass.warnings)
                warnings.append("auto mode escalated to a second, accurate-mode OCR pass")

        text_lines: tuple[EngineTextLine, ...] = final_result.text_lines
        line_texts = [line.text for line in text_lines]
        doc_tags = tag_document(line_texts)

        rtl_flags = [
            bool(tag.scripts) and tag.scripts[0] in _RTL_SCRIPTS for tag in doc_tags.line_tags
        ]

        try:
            fields = extract_fields(list(text_lines), rtl_flags)
        except Exception as exc:  # noqa: BLE001 - extraction must never crash a scan
            warnings.append(f"structured field extraction failed: {exc}")
            from receiptlingua.extract.types import StructuredFields

            fields = StructuredFields()

        text_line_dicts = []
        for line, tag in zip(text_lines, doc_tags.line_tags, strict=True):
            entry: dict[str, Any] = {
                "text": line.text,
                "bbox": line.bbox.to_dict(),
                "confidence": line.confidence,
                "status": line.status,
            }
            if tag.language.code != "unknown":
                entry["language"] = tag.language.code
            if tag.scripts:
                entry["script"] = tag.scripts[0]
            text_line_dicts.append(entry)

        width = load_result.width if load_result else int(pixels.shape[1])
        height = load_result.height if load_result else int(pixels.shape[0])
        img_format = (load_result.format or "unknown").lower() if load_result else "unknown"

        image_metadata: dict[str, Any] = {"width": width, "height": height, "format": img_format}
        if source_path and exif_orientation != 1:
            image_metadata["exif_orientation"] = exif_orientation

        elapsed_ms = (time.perf_counter() - start) * 1000.0

        return ReceiptResult(
            schema_version=SCHEMA_VERSION,
            engine=final_result.engine,
            engine_version=final_result.engine_version,
            mode=self.mode.value,
            image=image_metadata,
            processing_time_ms=round(elapsed_ms, 2),
            languages=list(doc_tags.languages),
            scripts=list(doc_tags.scripts),
            full_text=final_result.full_text,
            text_lines=text_line_dicts,
            warnings=warnings,
            fields=fields.to_dict(),
        )

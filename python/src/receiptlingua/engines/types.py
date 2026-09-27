"""Internal result types for the OCR engine layer.

These map directly onto the ``text_line``/``word`` definitions in
``protocol/schema/response.schema.json`` so the sidecar's protocol layer
can serialize an :class:`EngineResult` into a conformant response with no
lossy translation. Kept intentionally smaller than the full response
envelope -- structured field extraction (``fields``) is milestone 101-120
and is not produced here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# Mirrors $defs/recognition_status in response.schema.json.
RecognitionStatus = Literal["ok", "illegible", "truncated", "missing_region", "uncertain"]


@dataclass(frozen=True)
class BBox:
    """Axis-aligned bounding box in image pixel coordinates. Mirrors $defs/bbox."""

    x: float
    y: float
    width: float
    height: float

    def to_dict(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


@dataclass(frozen=True)
class EngineWord:
    """Mirrors $defs/word (minus ``line_index``, which the caller assigns)."""

    text: str
    bbox: BBox
    confidence: float
    status: RecognitionStatus = "ok"
    polygon: tuple[tuple[float, float], ...] | None = None
    language: str | None = None
    script: str | None = None


@dataclass(frozen=True)
class EngineTextLine:
    """Mirrors $defs/text_line."""

    text: str
    bbox: BBox
    confidence: float
    status: RecognitionStatus = "ok"
    polygon: tuple[tuple[float, float], ...] | None = None
    language: str | None = None
    script: str | None = None
    words: tuple[EngineWord, ...] = ()


@dataclass(frozen=True)
class EngineResult:
    """What a backend adapter's :meth:`OCREngine.recognize` returns.

    A thin, backend-agnostic container -- no structured field extraction,
    no full protocol envelope (schema_version/mode/image metadata are
    added by the sidecar's protocol layer, which has request-level
    context this layer does not need).
    """

    engine: str
    engine_version: str
    text_lines: tuple[EngineTextLine, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def full_text(self) -> str:
        return "\n".join(line.text for line in self.text_lines)

    @property
    def is_empty(self) -> bool:
        return len(self.text_lines) == 0

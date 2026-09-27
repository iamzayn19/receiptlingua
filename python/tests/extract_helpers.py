"""Shared test helper for building fake OCR text_line inputs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FakeBBox:
    x: float
    y: float
    width: float = 50.0
    height: float = 20.0


@dataclass(frozen=True)
class FakeTextLine:
    text: str
    bbox: FakeBBox


def make_lines(rows: list[tuple[str, float, float]]) -> list[FakeTextLine]:
    """Build FakeTextLine list from (text, x, y) tuples."""
    return [FakeTextLine(text=t, bbox=FakeBBox(x=x, y=y)) for t, x, y in rows]


def linear_lines(texts: list[str]) -> list[FakeTextLine]:
    """Build a simple top-to-bottom, single-column line list (y increases by row)."""
    return [FakeTextLine(text=t, bbox=FakeBBox(x=10.0, y=float(i) * 30.0)) for i, t in enumerate(texts)]

"""Reading-order reconstruction from OCR bounding boxes.

Backend OCR output is not guaranteed to arrive in natural reading order --
rotated pages, multi-column layouts, and stitched detections can hand back
``text_lines`` in a geometrically arbitrary order. This module reconstructs
a sensible top-to-bottom order by clustering lines into rows via y-overlap,
then orders each row left-to-right (or right-to-left for RTL script rows,
using the ``rtl`` flag callers derive from the langid module's per-line
script tags).

This is deliberately geometry-only: it does not attempt multi-column
detection (e.g. two side-by-side text blocks are treated as a single wide
row ordered by x, which is wrong for true multi-column receipts). That is a
known limitation, not a claim of general correctness -- most receipts are a
single narrow column, where this heuristic works well.
"""

from __future__ import annotations

from typing import Protocol


class HasBBox(Protocol):
    bbox: object  # duck-typed: needs .x, .y, .width, .height


def _y_center(line) -> float:
    return line.bbox.y + line.bbox.height / 2.0


def _row_overlap(a, b) -> bool:
    """True if two lines' vertical extents overlap by more than half of the shorter one's height."""
    a_top, a_bot = a.bbox.y, a.bbox.y + a.bbox.height
    b_top, b_bot = b.bbox.y, b.bbox.y + b.bbox.height
    overlap = min(a_bot, b_bot) - max(a_top, b_top)
    shorter = min(a.bbox.height, b.bbox.height) or 1.0
    return overlap > 0.5 * shorter


def reconstruct_reading_order(
    lines: list,
    rtl_flags: list[bool] | None = None,
) -> list[int]:
    """Return original ``lines`` indices reordered into a reading-order sequence.

    Rows are formed by grouping lines whose vertical spans substantially
    overlap (so lines that are merely close in y but on different "rows" of
    a slightly skewed scan can still end up together, which is intentional
    -- the alternative of pure fixed-band clustering breaks on any skew).
    Within each row, lines are ordered by x ascending (LTR) unless
    ``rtl_flags`` marks the row's majority as right-to-left, in which case
    the row orders by x descending.

    ``rtl_flags[i]`` should be True when ``lines[i]``'s script/language is
    right-to-left (e.g. Arabic, Urdu, Hebrew) -- callers typically derive
    this from ``receiptlingua.langid`` script tags.
    """
    n = len(lines)
    if n == 0:
        return []
    if rtl_flags is None:
        rtl_flags = [False] * n

    order_by_y = sorted(range(n), key=lambda i: _y_center(lines[i]))

    rows: list[list[int]] = []
    for i in order_by_y:
        placed = False
        for row in rows:
            # Compare against the row's most recently added line -- cheap
            # and good enough for the near-sorted-by-y sequence we iterate.
            if _row_overlap(lines[row[-1]], lines[i]):
                row.append(i)
                placed = True
                break
        if not placed:
            rows.append([i])

    result: list[int] = []
    for row in rows:
        row_rtl = sum(1 for i in row if rtl_flags[i]) > len(row) / 2
        row_sorted = sorted(row, key=lambda i: lines[i].bbox.x, reverse=row_rtl)
        result.extend(row_sorted)
    return result

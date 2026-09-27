"""Reading-order reconstruction tests."""

from __future__ import annotations

from receiptlingua.extract.reading_order import reconstruct_reading_order
from tests.extract_helpers import make_lines


def test_reorders_out_of_order_rows_top_to_bottom():
    lines = make_lines(
        [
            ("TOTAL 10.00", 10, 60),
            ("STORE NAME", 10, 0),
            ("2024-01-01", 10, 30),
        ]
    )
    order = reconstruct_reading_order(lines)
    assert [lines[i].text for i in order] == ["STORE NAME", "2024-01-01", "TOTAL 10.00"]


def test_orders_within_row_left_to_right_for_ltr():
    lines = make_lines(
        [
            ("world", 100, 0),
            ("hello", 0, 0),
        ]
    )
    order = reconstruct_reading_order(lines)
    assert [lines[i].text for i in order] == ["hello", "world"]


def test_orders_within_row_right_to_left_for_rtl():
    lines = make_lines(
        [
            ("جملة اولى", 100, 0),  # rightmost visually = first logically
            ("جملة ثانية", 0, 0),
        ]
    )
    order = reconstruct_reading_order(lines, rtl_flags=[True, True])
    # RTL row: higher x comes first.
    assert order == [0, 1]


def test_empty_input():
    assert reconstruct_reading_order([]) == []

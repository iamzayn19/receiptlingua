"""Tests for backend capability probing."""

from __future__ import annotations

from receiptlingua.engines.capabilities import probe_capabilities


def test_probe_capabilities_reports_cpu_count():
    report = probe_capabilities()
    assert report.cpu_count >= 1


def test_probe_capabilities_reports_known_backends():
    report = probe_capabilities()
    names = {b.name for b in report.backends}
    assert names == {"tesseract", "paddleocr"}


def test_probe_capabilities_gives_a_reason_for_every_backend():
    report = probe_capabilities()
    for backend in report.backends:
        assert backend.reason


def test_is_available_helper_matches_backend_list():
    report = probe_capabilities()
    for backend in report.backends:
        assert report.is_available(backend.name) == backend.available


def test_is_available_false_for_unknown_backend():
    report = probe_capabilities()
    assert report.is_available("not-a-real-backend") is False

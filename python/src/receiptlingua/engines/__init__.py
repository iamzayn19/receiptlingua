"""OCR engine abstraction layer.

Defines the backend-agnostic :class:`~receiptlingua.engines.base.OCREngine`
interface plus concrete adapters (Tesseract, PaddleOCR), a fast/accurate/auto
mode-selection policy, a model/language-data cache manager, and backend
capability probing. See ``ARCHITECTURE.md`` and
``docs/adr/0002-ocr-backend-selection.md``.
"""

from __future__ import annotations

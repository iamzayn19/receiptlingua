"""ReceiptLingua: offline-first multilingual receipt OCR."""

from receiptlingua.api import ReceiptOCR, ReceiptOCRError, ReceiptResult

__version__ = "0.1.0"

__all__ = ["ReceiptOCR", "ReceiptOCRError", "ReceiptResult", "__version__"]

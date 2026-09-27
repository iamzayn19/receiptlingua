"""Protocol-aligned error types for the OCR engine layer.

Error codes here must stay in sync with the ``code`` enum in
``protocol/schema/error.schema.json``. Engines and the cache manager raise
:class:`EngineError` (never a bare exception) for any failure that a client
across the protocol boundary needs to distinguish programmatically -- a
missing model, an unsupported backend, a malformed image, etc.
"""

from __future__ import annotations

from typing import Any, Literal

# Kept literal (not an Enum) so it mirrors the JSON schema's plain string
# enum exactly and serializes without extra conversion.
ErrorCode = Literal[
    "INVALID_IMAGE",
    "UNSUPPORTED_FORMAT",
    "MODEL_NOT_FOUND",
    "MODEL_DOWNLOAD_FAILED",
    "OCR_FAILED",
    "OUT_OF_MEMORY",
    "UNSUPPORTED_BACKEND",
    "INVALID_CONFIGURATION",
]


class EngineError(Exception):
    """Raised by engines/cache/mode-selection for any protocol-level failure.

    Carries a stable machine-readable ``code`` (see :data:`ErrorCode`) plus
    a human-readable ``message`` and optional structured ``details``, so
    callers can build a conformant ``error.schema.json`` envelope directly
    from ``to_dict()``.
    """

    def __init__(self, code: ErrorCode, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code: ErrorCode = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            error["details"] = self.details
        return error


class UnsupportedBackendError(EngineError):
    def __init__(self, backend: str, reason: str):
        super().__init__(
            "UNSUPPORTED_BACKEND",
            f"Backend '{backend}' is not available in this environment: {reason}",
            details={"backend": backend, "reason": reason},
        )


class ModelNotFoundError(EngineError):
    def __init__(self, backend: str, resource: str, search_paths: list[str]):
        super().__init__(
            "MODEL_NOT_FOUND",
            f"Required model/language data for backend '{backend}' not found: {resource}",
            details={"backend": backend, "resource": resource, "search_paths": search_paths},
        )


class OCRFailedError(EngineError):
    def __init__(self, backend: str, reason: str):
        super().__init__(
            "OCR_FAILED",
            f"OCR recognition failed on backend '{backend}': {reason}",
            details={"backend": backend, "reason": reason},
        )

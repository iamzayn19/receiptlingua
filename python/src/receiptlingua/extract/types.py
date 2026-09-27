"""Result types for structured receipt-field extraction.

These mirror the ``$defs/scalar_field``, ``$defs/line_item``,
``$defs/structured_fields`` and ``$defs/evidence`` definitions in
``protocol/schema/response.schema.json`` exactly, so a :class:`StructuredFields`
instance serializes into a schema-conformant ``fields`` object with no lossy
translation.

Mission constraint (see docs/COMMIT_PLAN.md 101-120): every field carries a
``status`` and, whenever a value is present, ``evidence`` pointing back at the
``text_lines`` it came from. A field that cannot be confidently extracted is
``missing`` -- never a guessed value with ``status: "ok"``. A value computed
from other fields (e.g. total = subtotal + tax) is ``inferred_field`` and its
evidence points at the lines the computation used, not at a nonexistent line.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

# Mirrors $defs/field_status.
FieldStatus = Literal["ok", "inferred_field", "uncertain", "missing"]


@dataclass(frozen=True)
class Evidence:
    """Mirrors $defs/evidence."""

    text_line_indices: tuple[int, ...] = ()
    word_indices: tuple[int, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.text_line_indices:
            out["text_line_indices"] = list(self.text_line_indices)
        if self.word_indices:
            out["word_indices"] = list(self.word_indices)
        return out

    def is_empty(self) -> bool:
        return not self.text_line_indices and not self.word_indices


@dataclass(frozen=True)
class ScalarField:
    """Mirrors $defs/scalar_field.

    ``status`` is required by the schema; ``value``/``confidence``/``evidence``
    are only emitted when present, matching ``additionalProperties: false``
    plus the schema's optional-property semantics.
    """

    status: FieldStatus
    value: Any = None
    confidence: float | None = None
    evidence: Evidence | None = None

    @staticmethod
    def missing() -> "ScalarField":
        """A field that could not be confidently extracted at all -- never a guess."""
        return ScalarField(status="missing")

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"status": self.status}
        if self.value is not None:
            out["value"] = self.value
        if self.confidence is not None:
            out["confidence"] = self.confidence
        if self.evidence is not None and not self.evidence.is_empty():
            out["evidence"] = self.evidence.to_dict()
        return out


@dataclass(frozen=True)
class LineItem:
    """Mirrors $defs/line_item."""

    status: FieldStatus
    description: ScalarField | None = None
    quantity: ScalarField | None = None
    unit_price: ScalarField | None = None
    item_total: ScalarField | None = None
    evidence: Evidence | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"status": self.status}
        for key in ("description", "quantity", "unit_price", "item_total"):
            val = getattr(self, key)
            if val is not None:
                out[key] = val.to_dict()
        if self.evidence is not None and not self.evidence.is_empty():
            out["evidence"] = self.evidence.to_dict()
        return out


_SCALAR_FIELD_NAMES = (
    "merchant",
    "merchant_address",
    "date",
    "time",
    "currency",
    "subtotal",
    "tax",
    "discounts",
    "total",
    "payment_method",
    "receipt_number",
)


@dataclass(frozen=True)
class StructuredFields:
    """Mirrors $defs/structured_fields."""

    merchant: ScalarField | None = None
    merchant_address: ScalarField | None = None
    date: ScalarField | None = None
    time: ScalarField | None = None
    currency: ScalarField | None = None
    subtotal: ScalarField | None = None
    tax: ScalarField | None = None
    discounts: ScalarField | None = None
    total: ScalarField | None = None
    payment_method: ScalarField | None = None
    receipt_number: ScalarField | None = None
    line_items: tuple[LineItem, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for name in _SCALAR_FIELD_NAMES:
            val = getattr(self, name)
            if val is not None:
                out[name] = val.to_dict()
        if self.line_items:
            out["line_items"] = [item.to_dict() for item in self.line_items]
        return out

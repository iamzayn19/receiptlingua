"""Deterministic synthetic receipt generation for benchmarking (milestone
171-185). See ``generator.py`` for the receipt generator and
``degrade.py`` for controlled, seeded image degradations.

Everything here is synthetic: no downloaded/scraped photos, per the
project's non-negotiable data-sourcing rule (see docs/COMMIT_PLAN.md and
datasets/registry.yaml). Ground truth is exact by construction -- the
generator wrote the text, so there is no annotation step or annotation
error to account for.
"""

from receiptlingua.synth.generator import SUPPORTED_LANGUAGES, GroundTruth, generate_receipt

__all__ = ["SUPPORTED_LANGUAGES", "GroundTruth", "generate_receipt"]

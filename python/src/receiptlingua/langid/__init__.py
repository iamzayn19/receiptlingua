"""Language/script detection for recognized OCR text.

Submodules:

- ``script``: Unicode script segmentation (per-character and per-run).
- ``identify``: language identification on plain text via py3langid.
- ``tagging``: combines the two into per-line and document-level tags
  shaped like the ``languages``/``scripts`` fields of
  ``protocol/schema/response.schema.json``.
- ``matrix``: loads the ``model_supported``/``receipt_verified`` language
  capability table (see ``data/language_matrix.json`` and
  ``LANGUAGES.md`` at the repo root).
"""

from __future__ import annotations

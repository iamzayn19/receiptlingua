# Architecture

## Processing pipeline

```
input validation
  -> image metadata normalization
  -> EXIF orientation
  -> receipt/document detection
  -> perspective correction
  -> crop
  -> orientation detection
  -> image-quality assessment
  -> preprocessing candidate generation
  -> text detection
  -> OCR
  -> script/language identification
  -> confidence analysis
  -> optional second-pass OCR
  -> candidate reconciliation
  -> reading-order reconstruction
  -> receipt field extraction
  -> output normalization
```

Each stage is implemented in `python/receiptlingua/pipeline/` as an
independently testable unit. Quality heuristics gate escalation: cheap
preprocessing runs first, and more expensive candidates/passes only run when
confidence is low or quality signals indicate degradation (fast/accurate/auto
modes).

## Cross-language design

```
+-------------------+        JSON protocol         +----------------------+
|  JS/TS client      | <---------------------------> |                      |
|  (npm package)     |                                |  Python sidecar      |
+-------------------+                                | (ML inference engine)|
                                                        |                      |
+-------------------+        JSON protocol         |                      |
|  Ruby client       | <---------------------------> |                      |
|  (gem)              |                                +----------------------+
+-------------------+
```

The Python sidecar is the single canonical OCR implementation. JavaScript and
Ruby clients are thin, fully-tested bindings that spawn/connect to the
sidecar and speak the versioned protocol defined in `protocol/`. This keeps
OCR logic in one place while giving each ecosystem an idiomatic native API.
The protocol is designed so the sidecar can later be replaced by a native
runtime without breaking the public JS/Ruby APIs.

The sidecar transport itself (stdio vs. a local socket, plus framing) was an
open item for a while; it's now decided -- newline-delimited JSON over
stdin/stdout -- see `docs/adr/0003-sidecar-transport.md`. The Python
`PaddleOCREngine` uses this to run a **persistent** sidecar daemon that
loads its model once and serves many `recognize()` calls, rather than the
earlier one-process-per-call stopgap.

## Engine abstraction

`python/receiptlingua/engines/` defines a common `OCREngine` interface with
interchangeable backends (PaddleOCR primary, Tesseract fallback, Surya for
benchmarking). Mode selection (`fast` / `accurate` / `auto`) is a policy layer
above the engine interface, not baked into any single backend.

## Data model

See `protocol/schema/` for the versioned JSON schema covering the full
output contract: metadata, languages/scripts, text lines, tokens,
polygons/boxes, confidence, warnings, structured fields, and provenance.

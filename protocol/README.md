# ReceiptLingua Protocol

This directory defines the JSON contract that all ReceiptLingua clients speak.
It is the single source of truth for what an OCR request/response looks like
— every language client (Python, JavaScript, Ruby) must honor this contract
rather than inventing its own shape.

## Why a protocol, not a shared library

The ML pipeline (preprocessing, OCR backends, structured extraction) lives in
a Python sidecar process, because the strongest OCR/ML ecosystem is Python's.
JavaScript and Ruby are thin clients: they start or attach to a local
sidecar and exchange JSON messages with it. Defining the JSON shape up front,
independent of any implementation, means:

- The three clients can be built and tested against fixtures without a
  working sidecar.
- Backend changes (swapping PaddleOCR for another engine, adding a mode)
  can't silently change what a JS or Ruby consumer receives.
- Conformance tests can run the same fixtures through every client's
  (de)serialization code and expect identical results.

## What's in this directory

- `schema/response.schema.json` — the OCR response envelope (JSON Schema,
  draft 2020-12).
- `schema/error.schema.json` — the error envelope used when a request fails.
- `fixtures/` — hand-written example payloads that validate against the
  schemas above, used for cross-language conformance testing later.
- `validate_fixtures.py` — validates every fixture against its schema.
- `VERSIONING.md` — how the protocol itself is versioned.

## Scope of this milestone

This milestone is schema-only. It defines the request/response *shape* and
the vocabulary (status enums, error codes, script/language tagging) that
every client will need to agree on. It does **not** implement:

- The actual sidecar process or its transport (stdio vs. a local Unix
  socket vs. something else — this is intentionally left open, see
  "Open questions" below and the future ADR it points to).
- Request framing (how one JSON message is delimited from the next on the
  wire).
- Any client-side (de)serialization code in `python/`, `javascript/`, or
  `ruby/` — those are later milestones.

## Open questions (not decided here)

- **Transport mechanism**: stdio (newline-delimited JSON over the sidecar's
  stdin/stdout) vs. a local Unix domain socket (or named pipe on Windows).
  Both are viable; the choice affects process lifecycle management, error
  recovery, and Windows support, and deserves its own ADR before the
  sidecar is implemented (see ADR 0003 referenced in the feasibility note).
- **Message framing**: length-prefixed frames vs. newline-delimited JSON
  vs. some other framing — depends on the transport choice above.

Both are called out explicitly so they aren't accidentally decided by
whatever the first implementation happens to do.

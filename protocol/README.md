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

- The actual sidecar process itself (this schema only defines the JSON
  shapes it exchanges).
- Any client-side (de)serialization code in `python/`, `javascript/`, or
  `ruby/` — those are later milestones.

## Transport (decided)

The open transport/framing question this section used to flag has been
resolved: **newline-delimited JSON over the sidecar's stdin/stdout**, no
Unix domain socket, no length-prefixed framing. See
`docs/adr/0003-sidecar-transport.md` for the full rationale and the
concrete wire format. It's implemented for the PaddleOCR sidecar in
`python/src/receiptlingua/engines/_paddle_sidecar_daemon.py` /
`paddleocr_engine.py`.

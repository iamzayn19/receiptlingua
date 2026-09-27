# receiptlingua (JavaScript/TypeScript client)

Thin TypeScript client for the ReceiptLingua OCR engine. See the
[root README](../README.md) for the project overview, and
[`ARCHITECTURE.md`](../ARCHITECTURE.md) / [`protocol/README.md`](../protocol/README.md)
for the cross-language design this package implements.

## Status

Not yet published to npm (no `npm login` has been done, and this package is
not yet exercised enough for a real release — see `docs/COMMIT_PLAN.md`).
Build and test locally from a repo checkout:

```bash
cd javascript
npm install
npm run build
npm test
```

## Usage

```ts
import { ReceiptOCR } from "receiptlingua";

const ocr = new ReceiptOCR();
const result = await ocr.scan("receipt.jpg");
console.log(result.full_text);
```

`scan()` also accepts a `Buffer` of raw image bytes.

## How it talks to the engine (important, read before relying on latency)

This client does **not** implement its own OCR. It spawns the Python
`receiptlingua` CLI (`python/src/receiptlingua/cli.py`, `scan --json`) as a
**subprocess per call** and parses its stdout against
`protocol/schema/response.schema.json` / `error.schema.json`. This requires
the Python package to be installed and importable (`pip install
receiptlingua`, or point `cliCommand` at a specific interpreter/venv).

This is a deliberate stopgap, not the final architecture. The transport
question itself is now decided (newline-delimited JSON over stdio -- see
`docs/adr/0003-sidecar-transport.md`), and the Python side
(`PaddleOCREngine`) now keeps a persistent PaddleOCR sidecar daemon warm
across repeated calls *within one Python process*. That does **not**
help this client yet: each `scan()` call here still spawns a brand-new
Python CLI subprocess, does exactly one scan, and exits -- so every call
still pays the full Python interpreter + model-load startup cost (this
can be hundreds of milliseconds to a few seconds depending on backend and
mode), because the CLI process (and therefore any daemon it spawned) does
not survive past that one call. If you need to scan many images fast,
prefer the Python API directly (construct one `ReceiptOCR` and call
`.scan()` on it repeatedly, which does reuse a warm PaddleOCR daemon), or
watch for a future long-lived server/daemon this client can be pointed at
instead of re-spawning the CLI per call.

If the CLI can't be found or run, `scan()` throws a `ReceiptLinguaError` with
`code: "CLI_NOT_FOUND"` and an actionable message, rather than a bare Node
`ENOENT`.

## Types

`ReceiptResult` and friends in `src/types.ts` are hand-written to mirror
`protocol/schema/response.schema.json` field-for-field (see the doc comment
at the top of that file for why hand-written rather than codegen'd from the
schema). Error codes in `ReceiptLinguaErrorCode` match
`protocol/schema/error.schema.json`'s enum, plus two client-local codes
(`CLI_NOT_FOUND`, `PROTOCOL_ERROR`) for failures that happen before/outside
the protocol envelope.

## Module format

Published as ESM only (`"type": "module"`, no CommonJS build). This is the
modern default for a new library; there is no existing CommonJS consumer to
support. If a CJS consumer becomes a real requirement later, add a second
`tsc` pass emitting `.cjs` rather than assuming it's needed up front.

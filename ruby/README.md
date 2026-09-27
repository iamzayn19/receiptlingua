# receiptlingua (Ruby client)

Thin Ruby client for the ReceiptLingua OCR engine. See the
[root README](../README.md) for the project overview, and
[`ARCHITECTURE.md`](../ARCHITECTURE.md) / [`protocol/README.md`](../protocol/README.md)
for the cross-language design this gem implements (the same design the
[JavaScript client](../javascript/README.md) follows).

## Status

Not yet published to RubyGems (no `gem signin` has been done in this
environment, and this gem is not yet exercised enough for a real release --
see `docs/COMMIT_PLAN.md`). Build and test locally from a repo checkout:

```bash
cd ruby
bundle install
bundle exec rspec
bundle exec rubocop
```

## Usage

```ruby
require "receiptlingua"

ocr = ReceiptLingua::ReceiptOCR.new
result = ocr.scan("receipt.jpg")
puts result.full_text
puts result.fields.total&.value
```

## Transport (read before assuming performance)

Like the JavaScript client, this gem does not talk to a persistent sidecar
daemon -- that transport (stdio vs. a local socket, plus framing) is still an
open ADR item in `protocol/README.md` and has not been built. Instead,
`ReceiptOCR#scan` shells out to the Python `receiptlingua` CLI
(`scan --json`) as a **fresh subprocess per call**, via `Open3`, and parses
its stdout as the `response.schema.json` envelope. This is correct and fully
protocol-conformant, but every call pays a full Python-interpreter-plus-
model-load startup cost, since nothing is kept warm between calls. The
concrete next step for whoever picks up the sidecar ADR is a persistent
daemon this client (and the JS client, which has the identical limitation)
can be pointed at instead of re-spawning per call.

## Errors

`ReceiptLingua::Error#code` carries a value from the same vocabulary as
`error.schema.json`'s `code` enum (`INVALID_IMAGE`, `UNSUPPORTED_FORMAT`,
`MODEL_NOT_FOUND`, `MODEL_DOWNLOAD_FAILED`, `OCR_FAILED`, `OUT_OF_MEMORY`,
`UNSUPPORTED_BACKEND`, `INVALID_CONFIGURATION`), plus two client-local codes
not part of the protocol: `CLI_NOT_FOUND` (raised as
`ReceiptLingua::CliNotFoundError` when the Python CLI can't be found/run --
with a message pointing at `pip install receiptlingua` or the `cli_command:`
option) and `PROTOCOL_ERROR` (raised as `ReceiptLingua::ProtocolError` when
the CLI's output isn't valid JSON, or doesn't match the expected envelope).

# Technical Feasibility Note

Date: 2026-09-27

## Naming

`receiptlingua` is unclaimed on GitHub, PyPI, npm, and RubyGems as of this date
(all four lookups returned 404 / not found). No rename needed.

## Environment

- Machine: Apple M5 (arm64, macOS Darwin 25.6.0)
- Python 3.14.3 (Homebrew), no `uv` installed yet
- Node 24.16.0 / 20.12.1 available via asdf, project pinned to 24.16.0
- Ruby 3.2.11 with bundler 3.4.19
- `gh` CLI authenticated as `iamzayn19` (repo, gist, read:org scopes)
- npm: not logged in (publishing blocked until owner runs `npm login`)
- RubyGems: no `~/.gem/credentials` (publishing blocked until owner runs `gem signin`)

## OCR backend strategy

PaddleOCR (PP-OCRv4/v5 multilingual recognition) is the strongest current
open-source candidate for broad multilingual receipt OCR: Apache-2.0 licensed,
actively maintained, wide script coverage (Latin, Arabic, Devanagari-family,
CJK, Cyrillic). Surya (GPL/AGPL-adjacent licensing needs re-check per release)
is evaluated as a secondary/benchmark-only backend. Tesseract is kept as an
optional low-dependency fallback baseline (Apache-2.0).

No cloud OCR/VLM API is used for the default pipeline. Apple Silicon (MPS)
acceleration is investigated for the Python sidecar but backend selection
must degrade gracefully to CPU on Linux/Windows CI.

## Cross-language architecture

Python hosts the ML sidecar (protocol server) since the ML ecosystem is
strongest there. JavaScript and Ruby ship as thin protocol clients that talk
to a local sidecar process over a documented JSON protocol (see `protocol/`).
This keeps a single canonical OCR implementation while giving all three
ecosystems a native-feeling API.

## Risks tracked in later ADRs

- Model license/redistribution terms per PaddleOCR model release (ADR 0002)
- Protocol transport choice (stdio/socket) for the sidecar (ADR 0003)
- Dataset licensing for benchmark corpus (ADR 0004)

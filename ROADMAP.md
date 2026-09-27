# Roadmap

Tracked in detail in [docs/COMMIT_PLAN.md](docs/COMMIT_PLAN.md). High-level
milestones toward a first real public release:

## Milestone 1 — Foundations (in progress)
- Repo bootstrap, licensing, governance docs
- Cross-language JSON protocol + schema versioning
- ADRs for OCR backend and dataset choices

## Milestone 2 — Preprocessing pipeline
- Full staged pipeline: orientation, perspective correction, deskew,
  quality-adaptive preprocessing candidates

## Milestone 3 — OCR engine abstraction
- PaddleOCR primary backend, Tesseract fallback, Surya benchmark backend
- Fast / accurate / auto mode selection
- Offline-first model caching

## Milestone 4 — Language & script intelligence
- Mixed-script and RTL handling
- `model_supported` vs `receipt_verified` language matrix

## Milestone 5 — Structured extraction
- Merchant/date/total/line-item extraction with evidence provenance

## Milestone 6 — Three ecosystems
- Python package, TypeScript/npm client, Ruby gem — all backed by one
  protocol and one canonical engine

## Milestone 7 — Datasets & benchmarking
- Licensed dataset registry, synthetic + corruption pipeline,
  10,000+ case benchmark, published BENCHMARKS.md

## Milestone 8 — Release readiness
- Website, CI/CD, security scanning, SBOM, first tagged pre-release

Not yet scheduled: automatic package publishing (requires owner-run
`npm login` / `gem signin` / PyPI trusted publishing setup — see blockers in
[docs/adr/](docs/adr/)).

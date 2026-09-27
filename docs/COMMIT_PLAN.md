# Commit Plan (target: ~200 atomic commits)

This plan is directional, not a rigid script. Commits will be added, split, or
merged as implementation reveals better boundaries; this file is updated as
that happens rather than followed blindly.

## 1-15 Bootstrap
1. chore: initialize monorepo skeleton
2. docs: add feasibility note (ADR 0001)
3. docs: add commit plan
4. chore: add LICENSE (Apache-2.0)
5. chore: add NOTICE
6. docs: add README skeleton
7. docs: add CONTRIBUTING
8. docs: add CODE_OF_CONDUCT
9. docs: add SECURITY policy
10. docs: add SUPPORT
11. docs: add ROADMAP
12. docs: add ARCHITECTURE overview
13. chore: add .gitignore for python/js/ruby/models/datasets
14. chore: add EditorConfig and base lint configs
15. chore: add FUNDING.yml placeholder (no identifiers yet)

## 16-30 Protocol/schema
16-30. Define JSON schema_version 0.1, request/response envelope, error codes,
language/script objects, box/polygon types, protocol conformance fixtures,
protocol README, versioning policy.

## 31-55 Preprocessing
31-55. Image loading/validation, EXIF normalization, orientation detection,
document boundary detection, perspective correction, deskew, CLAHE,
adaptive threshold, denoise, sharpen, gamma/illumination correction,
quality-heuristic scorer, candidate pipeline orchestration, unit tests per
stage.

## 56-80 OCR engine abstraction
56-80. Engine interface, PaddleOCR backend adapter, Tesseract fallback
adapter, Surya benchmark-only adapter, fast/accurate/auto mode selection,
model download/cache manager, offline error handling, backend capability
probing (MPS/CPU/CUDA), batching support.

## 81-100 Language/script detection
81-100. Unicode script segmentation, line/region-level script tagging,
language ID integration, mixed-script/RTL handling, confidence thresholds,
model_supported vs receipt_verified matrix generation.

## 101-120 Structured receipt extraction
101-120. Reading-order reconstruction, merchant/date/time/currency/total
extraction rules, line-item table extraction, evidence/provenance linking,
uncertain/illegible/truncated/missing_region field states.

## 121-140 Python packaging/CLI
121-140. `receiptlingua` package layout, `ReceiptOCR` API, CLI (`scan`,
`languages`, `models`, `doctor`, `benchmark`, `cache info`), pyproject/uv
setup, ruff/mypy/pytest wiring, packaging smoke tests.

## 141-155 JavaScript client
141-155. TypeScript client package, sidecar process manager, protocol
client, vitest suite, eslint/prettier config, npm packaging.

## 156-170 Ruby client
156-170. Gem structure, sidecar client, RSpec suite, rubocop config,
gemspec, packaging.

## 171-185 Datasets/benchmarking
171-185. `datasets/registry.yaml`, license-audited downloader scripts,
synthetic receipt generator, deterministic corruption pipeline, benchmark
harness, CER/WER/field-accuracy metrics, BENCHMARKS.md report generation.

## 186-195 Website/docs/security/release automation
186-195. GitHub Pages site, LANGUAGES.md matrix page, CI workflows
(python/node/ruby/lint/security), SBOM generation, Dependabot config,
release workflow drafts (no auto-publish yet).

## 196-200 Release hardening
196-200. Cross-language conformance test run, offline-mode validation,
first real tagged pre-release, final README pass, blockers doc for
owner-only actions (npm login, gem signin, GitHub repo creation confirm).

---

Status: commits 1-15 done; 16-30 (protocol/schema) done as of 2026-09-27.
Actual commit count for 16-30 was ~11 rather than 15, since the schema work
naturally grouped into fewer, larger atomic steps (envelope, languages,
text lines, structured fields, error schema, versioning, script, and one
commit per fixture). Transport mechanism (stdio vs. Unix socket) remains
an open question for a future ADR before milestone 31+ needs it directly,
and is not blocking — the sidecar isn't implemented yet.

31-55 (preprocessing) done as of 2026-09-27, in ~12 commits rather than the
~25 implied by the range (each stage plus its tests landed as one atomic
commit, and fixture generation/plan scaffolding were grouped rather than
split further). This is also the first code under `python/`, so minimal
packaging scaffolding was added alongside it (not the full 121-140
packaging/CLI milestone): `python/pyproject.toml`, a `src/receiptlingua`
layout, ruff+pytest config. Dependencies chosen: numpy, pillow, and
opencv-python-headless (all BSD/permissive-licensed, verified installable
in this environment on Python 3.14). `uv` was checked again and is still
not installed, so plain `venv`+`pip` was used.

Implemented under `python/receiptlingua/pipeline/preprocess/`: image
loading/validation (decompression-bomb and malformed-file guards), EXIF
orientation normalization, deskew, a v0 heuristic perspective/document-
boundary correction (documented as a simplified approach, not a trained
model), grayscale normalization, CLAHE, adaptive thresholding, fast/
accurate denoising, unsharp-mask sharpening, gamma/illumination
correction, an image-quality heuristic scorer (blur/contrast/brightness),
and a pipeline orchestrator that gates accurate-mode stages on the
quality score instead of always running every technique. 74 tests pass
against synthetic fixtures generated in-repo (no downloaded photos),
including corrupt/zero-byte/non-image/decompression-bomb edge cases.

Deviation: adaptive thresholding and denoise/sharpen are implemented as
standalone, independently testable modules but are not both wired into
the orchestrator's default candidate (thresholding is left for the OCR
engine layer to invoke per-backend, since some OCR backends prefer
grayscale input over a hard binary mask). Open question for a future ADR:
whether the v0 perspective-correction heuristic needs to be replaced by a
trained document-boundary model once real-world (non-synthetic) receipt
photos are available to benchmark against.

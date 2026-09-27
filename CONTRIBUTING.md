# Contributing

## Getting started

A contributor should be able to clone, bootstrap, run fast tests, and make a
small change without downloading models or datasets.

```bash
git clone <repo>
cd receiptlingua
# Python
cd python && uv sync && uv run pytest -m "not slow"
# JavaScript
cd ../javascript && npm install && npm test
# Ruby
cd ../ruby && bundle install && bundle exec rspec
```

Fast tests use small fixture images committed in `tests/fixtures/` under
compatible licensing — never real receipts or downloaded model weights.

## Commit style

Conventional-style, meaningful commits, e.g.:

```
feat(preprocess): add perspective correction
fix(ruby): preserve UTF-8 OCR output
test(ocr): cover mixed Tamil and English receipt
```

Avoid trivial or placeholder commits.

## Pull requests

- Keep PRs scoped to one change
- Add or update tests alongside the code they cover
- Run lint/format/type-check locally before opening a PR
- Update relevant docs (LANGUAGES.md, BENCHMARKS.md, protocol schema) when
  behavior changes

## Adding language/backend support

Any change affecting language coverage must update the language support
matrix and clearly separate `model_supported` from `receipt_verified`
claims — see [LANGUAGES.md](LANGUAGES.md).

## Adding datasets

Datasets must go through `datasets/registry.yaml` with a documented license
and redistribution permission before use. Do not commit dataset files
directly to git.

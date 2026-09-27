# ReceiptLingua

Multilingual receipt OCR that runs fully offline after model download — no
paid API required. Handles the receipts other OCR tools give up on: faded,
crumpled, thermal, torn, mixed-script, rotated, badly photographed.

Status: early development (pre-0.1). See [ROADMAP.md](ROADMAP.md) and
[docs/COMMIT_PLAN.md](docs/COMMIT_PLAN.md) for current progress.

## Quick start

### Python

```bash
pip install receiptlingua
```

```python
from receiptlingua import ReceiptOCR

ocr = ReceiptOCR()
result = ocr.scan("receipt.jpg")
print(result.full_text)
```

### JavaScript / TypeScript

```bash
npm install receiptlingua
```

```ts
import { ReceiptOCR } from "receiptlingua";

const ocr = new ReceiptOCR();
const result = await ocr.scan("receipt.jpg");
```

### Ruby

```bash
gem install receiptlingua
```

```ruby
require "receiptlingua"

ocr = ReceiptLingua::ReceiptOCR.new
result = ocr.scan("receipt.jpg")
```

## Design principles

- No cloud OCR/VLM API required for normal operation
- No telemetry, no hidden uploads
- Honest language claims: `model_supported` vs `receipt_verified` (see
  [LANGUAGES.md](LANGUAGES.md))
- Never hallucinate text that isn't physically there — degraded regions are
  reported as `illegible` / `missing_region`, not guessed

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the processing pipeline and
cross-language protocol design.

## License

Apache License 2.0. See [LICENSE](LICENSE), [NOTICE](NOTICE),
[MODEL_LICENSES.md](MODEL_LICENSES.md), and
[DATASET_LICENSES.md](DATASET_LICENSES.md).

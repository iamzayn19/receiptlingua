import { execFile } from "node:child_process";
import { existsSync } from "node:fs";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { describe, expect, it } from "vitest";

import { ReceiptOCR } from "../src/receipt-ocr.js";

const execFileAsync = promisify(execFile);

const __dirname = dirname(fileURLToPath(import.meta.url));
const FIXTURE = join(__dirname, "..", "..", "python", "tests", "fixtures", "receipt_text_eng.png");

/**
 * Real end-to-end test: shells out to the ACTUAL installed Python
 * `receiptlingua` CLI (python/.venv/bin/receiptlingua if present, else
 * whatever `receiptlingua` resolves to on PATH) against a real synthetic
 * fixture from the Python test suite, and asserts a real, schema-shaped,
 * non-empty result.
 *
 * Mirrors the skip-if-missing pattern used by the Python tests for missing
 * langpacks: if no working `receiptlingua` CLI is importable in whatever
 * environment runs this, the test SKIPS rather than fails, since this repo's
 * CI/dev environments may not always have the Python package installed.
 */

async function findCliCommand(): Promise<string[] | null> {
  const venvBin = join(__dirname, "..", "..", "python", ".venv", "bin", "receiptlingua");
  if (existsSync(venvBin)) {
    try {
      await execFileAsync(venvBin, ["--version"]);
      return [venvBin];
    } catch {
      // fall through to PATH lookup
    }
  }
  try {
    await execFileAsync("receiptlingua", ["--version"]);
    return ["receiptlingua"];
  } catch {
    return null;
  }
}

const cliCommand = await findCliCommand();

describe.skipIf(cliCommand === null)("ReceiptOCR.scan (real Python CLI integration)", () => {
  it("returns a real, schema-shaped, non-empty result for a synthetic fixture", async () => {
    expect(existsSync(FIXTURE)).toBe(true);

    const ocr = new ReceiptOCR({ cliCommand: cliCommand! });
    const result = await ocr.scan(FIXTURE);

    expect(result.schema_version).toMatch(/^\d+\.\d+\.\d+$/);
    expect(typeof result.engine).toBe("string");
    expect(result.engine.length).toBeGreaterThan(0);
    expect(["fast", "accurate", "auto"]).toContain(result.mode);
    expect(result.image.width).toBeGreaterThan(0);
    expect(result.image.height).toBeGreaterThan(0);
    expect(Array.isArray(result.text_lines)).toBe(true);
    expect(Array.isArray(result.languages)).toBe(true);
    expect(typeof result.full_text).toBe("string");
    // This fixture has real rendered receipt text, so OCR should recover
    // something non-trivial (not asserting exact text -- that's the
    // Python engine's own test suite's job).
    expect(result.full_text.trim().length).toBeGreaterThan(0);
    expect(result.fields).toBeTypeOf("object");
  });

  it("scans from a Buffer as well as a path", async () => {
    const { readFile } = await import("node:fs/promises");
    const buffer = await readFile(FIXTURE);

    const ocr = new ReceiptOCR({ cliCommand: cliCommand! });
    const result = await ocr.scan(buffer);

    expect(result.full_text.trim().length).toBeGreaterThan(0);
  });

  it("raises a typed ReceiptLinguaError for a nonexistent path via the real CLI", async () => {
    const ocr = new ReceiptOCR({ cliCommand: cliCommand! });
    await expect(ocr.scan("/definitely/does/not/exist.png")).rejects.toMatchObject({
      code: "INVALID_IMAGE",
    });
  });
});

if (cliCommand === null) {
  // Vitest still needs at least one assertion path to not report an empty
  // file as a failure in some configurations; describe.skipIf already
  // handles this, but log why for local debugging.
  console.warn(
    "[receipt-ocr.integration.test] Skipping: no working `receiptlingua` CLI found " +
      "(checked python/.venv/bin/receiptlingua and PATH). Run `pip install -e python` " +
      "or equivalent to enable this test.",
  );
}

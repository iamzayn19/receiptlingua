import { EventEmitter } from "node:events";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { ReceiptOCR } from "../src/receipt-ocr.js";
import { ReceiptLinguaError } from "../src/errors.js";

const spawnMock = vi.hoisted(() => vi.fn());

vi.mock("node:child_process", () => ({
  spawn: spawnMock,
}));

/** Builds a fake ChildProcess-like EventEmitter with stdout/stderr streams. */
function fakeChild() {
  const child = new EventEmitter() as EventEmitter & {
    stdout: EventEmitter;
    stderr: EventEmitter;
    kill: () => void;
  };
  child.stdout = new EventEmitter();
  child.stderr = new EventEmitter();
  child.kill = vi.fn();
  return child;
}

type FakeChild = EventEmitter & { stdout: EventEmitter; stderr: EventEmitter; kill: () => void };

function emitClose(child: FakeChild, stdout: string, stderr: string, code: number) {
  if (stdout) child.stdout.emit("data", Buffer.from(stdout));
  if (stderr) child.stderr.emit("data", Buffer.from(stderr));
  child.emit("close", code);
}

const VALID_RESULT = {
  schema_version: "0.1.0",
  engine: "tesseract",
  engine_version: "5.5.2",
  mode: "auto",
  image: { width: 10, height: 10, format: "png" },
  processing_time_ms: 12.3,
  languages: [{ code: "en", confidence: 0.9 }],
  scripts: ["Latn"],
  full_text: "HELLO",
  text_lines: [],
  warnings: [],
  fields: {},
};

describe("ReceiptOCR.scan (mocked subprocess)", () => {
  beforeEach(() => {
    spawnMock.mockReset();
  });

  it("parses a successful JSON response into a ReceiptResult", async () => {
    const child = fakeChild();
    spawnMock.mockReturnValue(child);

    const ocr = new ReceiptOCR();
    const promise = ocr.scan("/tmp/whatever.png");
    emitClose(child, JSON.stringify(VALID_RESULT), "", 0);

    const result = await promise;
    expect(result.full_text).toBe("HELLO");
    expect(result.engine).toBe("tesseract");

    const [program, args] = spawnMock.mock.calls[0];
    expect(program).toBe("receiptlingua");
    expect(args).toContain("scan");
    expect(args).toContain("/tmp/whatever.png");
    expect(args).toContain("--json");
  });

  it("passes mode and languages through to the CLI args", async () => {
    const child = fakeChild();
    spawnMock.mockReturnValue(child);

    const ocr = new ReceiptOCR({ mode: "accurate", languages: ["en", "ta"] });
    const promise = ocr.scan("/tmp/x.png");
    emitClose(child, JSON.stringify(VALID_RESULT), "", 0);
    await promise;

    const [, args] = spawnMock.mock.calls[0];
    expect(args).toEqual(expect.arrayContaining(["--mode", "accurate", "--lang", "en,ta"]));
  });

  it("maps a protocol error envelope (non-zero exit) to a ReceiptLinguaError with matching code", async () => {
    const child = fakeChild();
    spawnMock.mockReturnValue(child);

    const errorEnvelope = {
      schema_version: "0.1.0",
      error: {
        code: "INVALID_IMAGE",
        message: "Invalid image: unreadable",
        details: { reason: "unreadable" },
      },
    };

    const ocr = new ReceiptOCR();
    const promise = ocr.scan("/tmp/bad.png");
    emitClose(child, JSON.stringify(errorEnvelope), "", 1);

    await expect(promise).rejects.toMatchObject({
      code: "INVALID_IMAGE",
      message: "Invalid image: unreadable",
    });
    await expect(promise.catch((e) => e)).resolves.toBeInstanceOf(ReceiptLinguaError);
  });

  it("raises PROTOCOL_ERROR when stdout is not valid JSON", async () => {
    const child = fakeChild();
    spawnMock.mockReturnValue(child);

    const ocr = new ReceiptOCR();
    const promise = ocr.scan("/tmp/x.png");
    emitClose(child, "not json at all", "", 0);

    await expect(promise).rejects.toMatchObject({ code: "PROTOCOL_ERROR" });
  });

  it("raises PROTOCOL_ERROR when JSON is valid but doesn't match the response shape", async () => {
    const child = fakeChild();
    spawnMock.mockReturnValue(child);

    const ocr = new ReceiptOCR();
    const promise = ocr.scan("/tmp/x.png");
    emitClose(child, JSON.stringify({ unexpected: true }), "", 0);

    await expect(promise).rejects.toMatchObject({ code: "PROTOCOL_ERROR" });
  });

  it("raises OCR_FAILED with stderr context when exit is non-zero and output isn't an error envelope", async () => {
    const child = fakeChild();
    spawnMock.mockReturnValue(child);

    const ocr = new ReceiptOCR();
    const promise = ocr.scan("/tmp/x.png");
    emitClose(child, "", "traceback: boom", 2);

    await expect(promise).rejects.toMatchObject({ code: "OCR_FAILED" });
    await expect(promise.catch((e) => e.message)).resolves.toContain("boom");
  });

  it("raises CLI_NOT_FOUND with an actionable message when spawn fails with ENOENT", async () => {
    spawnMock.mockImplementation(() => {
      const err = new Error("spawn receiptlingua ENOENT") as NodeJS.ErrnoException;
      err.code = "ENOENT";
      throw err;
    });

    const ocr = new ReceiptOCR();
    await expect(ocr.scan("/tmp/x.png")).rejects.toMatchObject({ code: "CLI_NOT_FOUND" });
    await expect(ocr.scan("/tmp/x.png").catch((e) => e.message)).resolves.toMatch(
      /pip install receiptlingua/,
    );
  });

  it("uses a custom cliCommand when provided", async () => {
    const child = fakeChild();
    spawnMock.mockReturnValue(child);

    const ocr = new ReceiptOCR({ cliCommand: ["/venv/bin/python", "-m", "receiptlingua.cli"] });
    const promise = ocr.scan("/tmp/x.png");
    emitClose(child, JSON.stringify(VALID_RESULT), "", 0);
    await promise;

    const [program, args] = spawnMock.mock.calls[0];
    expect(program).toBe("/venv/bin/python");
    expect(args[0]).toBe("-m");
    expect(args[1]).toBe("receiptlingua.cli");
    expect(args).toContain("scan");
  });
});

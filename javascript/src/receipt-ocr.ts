import { spawn } from "node:child_process";
import { mkdtemp, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { ReceiptLinguaError } from "./errors.js";
import type { ProcessingMode, ReceiptErrorEnvelope, ReceiptResult } from "./types.js";

export interface ReceiptOCROptions {
  /**
   * Full command used to invoke the Python CLI, as argv (program + leading
   * args). Defaults to `["receiptlingua"]`, i.e. the console script installed
   * by `pip install receiptlingua` (see `python/pyproject.toml`'s
   * `[project.scripts]`), resolved via PATH.
   *
   * Override this to point at a specific interpreter/venv instead, e.g.
   * `["/path/to/venv/bin/python", "-m", "receiptlingua.cli"]`.
   */
  cliCommand?: string[];
  /** Processing mode passed through to the CLI's `--mode`. Defaults to "auto". */
  mode?: ProcessingMode;
  /** Comma-joined language codes passed through to the CLI's `--lang`. */
  languages?: string[];
  /** Kill the subprocess and raise if it runs longer than this. Default: none. */
  timeoutMs?: number;
  /**
   * Sets `RECEIPTLINGUA_CACHE_DIR` for the subprocess, matching the Python
   * `CacheManager.from_env()` lookup order (see
   * `python/src/receiptlingua/engines/cache.py`).
   */
  cacheDir?: string;
}

interface ScanOptions {
  mode?: ProcessingMode;
  languages?: string[];
  timeoutMs?: number;
}

const DEFAULT_CLI_COMMAND = ["receiptlingua"];

/**
 * Thin JS client for the ReceiptLingua OCR engine.
 *
 * Transport note (see `ARCHITECTURE.md` / `protocol/README.md`): the real
 * sidecar transport (stdio or a local socket, with its own framing) is an
 * open ADR item and has not been built yet. As a stopgap, this client shells
 * out to the already-working Python `receiptlingua` CLI (`scan --json`) as a
 * fresh subprocess *per call*. This is correct and fully protocol-conformant,
 * but it is NOT the final transport: every `scan()` call pays the full
 * Python/model-load startup cost (hundreds of ms to seconds depending on
 * backend), because nothing is kept warm between calls. A persistent
 * sidecar daemon (spawned once, communicated with over stdio/socket) is the
 * documented next step for whoever picks up that ADR.
 */
export class ReceiptOCR {
  private readonly cliCommand: string[];
  private readonly defaultMode?: ProcessingMode;
  private readonly defaultLanguages?: string[];
  private readonly defaultTimeoutMs?: number;
  private readonly cacheDir?: string;

  constructor(options: ReceiptOCROptions = {}) {
    this.cliCommand = options.cliCommand ?? DEFAULT_CLI_COMMAND;
    this.defaultMode = options.mode;
    this.defaultLanguages = options.languages;
    this.defaultTimeoutMs = options.timeoutMs;
    this.cacheDir = options.cacheDir;
  }

  /**
   * Runs OCR + field extraction on a receipt image.
   *
   * @param pathOrBuffer Path to an image file, or raw image bytes as a Buffer
   *   (written to a temp file, since the underlying CLI takes a path).
   */
  async scan(pathOrBuffer: string | Buffer, options: ScanOptions = {}): Promise<ReceiptResult> {
    if (typeof pathOrBuffer === "string") {
      return this.scanPath(pathOrBuffer, options);
    }
    return this.scanBuffer(pathOrBuffer, options);
  }

  private async scanBuffer(buffer: Buffer, options: ScanOptions): Promise<ReceiptResult> {
    const dir = await mkdtemp(join(tmpdir(), "receiptlingua-"));
    const tmpPath = join(dir, "input");
    try {
      await writeFile(tmpPath, buffer);
      return await this.scanPath(tmpPath, options);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  }

  private async scanPath(path: string, options: ScanOptions): Promise<ReceiptResult> {
    const mode = options.mode ?? this.defaultMode;
    const languages = options.languages ?? this.defaultLanguages;
    const timeoutMs = options.timeoutMs ?? this.defaultTimeoutMs;

    const [program, ...leadingArgs] = this.cliCommand;
    const args = [...leadingArgs, "scan", path, "--json"];
    if (mode) {
      args.push("--mode", mode);
    }
    if (languages && languages.length > 0) {
      args.push("--lang", languages.join(","));
    }

    const env = { ...process.env };
    if (this.cacheDir) {
      env.RECEIPTLINGUA_CACHE_DIR = this.cacheDir;
    }

    const { stdout, stderr, exitCode } = await this.run(program, args, env, timeoutMs);

    if (exitCode !== 0) {
      throw this.errorFromFailure(stdout, stderr, exitCode);
    }

    return this.parseResult(stdout);
  }

  private run(
    program: string,
    args: string[],
    env: NodeJS.ProcessEnv,
    timeoutMs: number | undefined,
  ): Promise<{ stdout: string; stderr: string; exitCode: number | null }> {
    return new Promise((resolve, reject) => {
      let child: ReturnType<typeof spawn>;
      try {
        child = spawn(program, args, { env });
      } catch (err) {
        reject(this.spawnErrorToReceiptLinguaError(err, program));
        return;
      }

      let stdout = "";
      let stderr = "";
      let timedOut = false;
      let timer: NodeJS.Timeout | undefined;

      if (timeoutMs) {
        timer = setTimeout(() => {
          timedOut = true;
          child.kill();
        }, timeoutMs);
      }

      child.stdout?.on("data", (chunk: Buffer) => {
        stdout += chunk.toString("utf8");
      });
      child.stderr?.on("data", (chunk: Buffer) => {
        stderr += chunk.toString("utf8");
      });

      child.on("error", (err) => {
        if (timer) clearTimeout(timer);
        reject(this.spawnErrorToReceiptLinguaError(err, program));
      });

      child.on("close", (code) => {
        if (timer) clearTimeout(timer);
        if (timedOut) {
          reject(
            new ReceiptLinguaError(
              "OCR_FAILED",
              `receiptlingua CLI timed out after ${timeoutMs}ms`,
              { program, args },
            ),
          );
          return;
        }
        resolve({ stdout, stderr, exitCode: code });
      });
    });
  }

  private spawnErrorToReceiptLinguaError(err: unknown, program: string): ReceiptLinguaError {
    const nodeErr = err as NodeJS.ErrnoException;
    if (nodeErr && nodeErr.code === "ENOENT") {
      return new ReceiptLinguaError(
        "CLI_NOT_FOUND",
        `Could not find or run "${program}". The ReceiptLingua Python engine must be ` +
          `installed and on PATH (\`pip install receiptlingua\`), or pass an explicit ` +
          `\`cliCommand\` to ReceiptOCR pointing at the interpreter/venv to use, e.g. ` +
          `new ReceiptOCR({ cliCommand: ["/path/to/venv/bin/python", "-m", "receiptlingua.cli"] }).`,
        { program, originalCode: nodeErr.code },
      );
    }
    return new ReceiptLinguaError(
      "CLI_NOT_FOUND",
      `Failed to launch "${program}": ${nodeErr?.message ?? String(err)}`,
      { program },
    );
  }

  private errorFromFailure(
    stdout: string,
    stderr: string,
    exitCode: number | null,
  ): ReceiptLinguaError {
    const candidate = stdout.trim().length > 0 ? stdout : stderr;
    const parsed = this.tryParseJson(candidate);
    if (parsed && this.looksLikeErrorEnvelope(parsed)) {
      const envelope = parsed as ReceiptErrorEnvelope;
      return new ReceiptLinguaError(
        envelope.error.code,
        envelope.error.message,
        envelope.error.details ?? {},
      );
    }
    return new ReceiptLinguaError(
      "OCR_FAILED",
      `receiptlingua CLI exited with code ${exitCode}: ${stderr.trim() || stdout.trim() || "(no output)"}`,
      { exitCode, stderr: stderr.trim(), stdout: stdout.trim() },
    );
  }

  private parseResult(stdout: string): ReceiptResult {
    const parsed = this.tryParseJson(stdout);
    if (parsed === undefined) {
      throw new ReceiptLinguaError(
        "PROTOCOL_ERROR",
        "receiptlingua CLI produced output that was not valid JSON.",
        { stdout: stdout.slice(0, 2000) },
      );
    }
    if (this.looksLikeErrorEnvelope(parsed)) {
      const envelope = parsed as ReceiptErrorEnvelope;
      throw new ReceiptLinguaError(
        envelope.error.code,
        envelope.error.message,
        envelope.error.details ?? {},
      );
    }
    if (!this.looksLikeResultEnvelope(parsed)) {
      throw new ReceiptLinguaError(
        "PROTOCOL_ERROR",
        "receiptlingua CLI produced JSON that does not match the expected response shape.",
        { received: parsed },
      );
    }
    return parsed as ReceiptResult;
  }

  private tryParseJson(text: string): unknown {
    try {
      return JSON.parse(text);
    } catch {
      return undefined;
    }
  }

  private looksLikeErrorEnvelope(value: unknown): value is ReceiptErrorEnvelope {
    return (
      typeof value === "object" &&
      value !== null &&
      "error" in value &&
      typeof (value as { error?: unknown }).error === "object" &&
      (value as { error?: { code?: unknown } }).error !== null &&
      typeof (value as { error: { code?: unknown } }).error.code === "string"
    );
  }

  private looksLikeResultEnvelope(value: unknown): value is ReceiptResult {
    if (typeof value !== "object" || value === null) return false;
    const required = [
      "schema_version",
      "engine",
      "engine_version",
      "mode",
      "image",
      "processing_time_ms",
      "languages",
      "scripts",
      "full_text",
      "text_lines",
      "warnings",
      "fields",
    ];
    return required.every((key) => key in (value as Record<string, unknown>));
  }
}

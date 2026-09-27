import type { ReceiptLinguaErrorCode } from "./types.js";

/**
 * Error type for every failure this client can raise, whether it came from
 * the Python sidecar's own error envelope (`protocol/schema/error.schema.json`)
 * or from a local problem invoking it (missing interpreter, malformed output).
 *
 * Callers should branch on `.code`, not on `.message` (message text may
 * change between versions, per the protocol's own doc comment on `message`).
 */
export class ReceiptLinguaError extends Error {
  public readonly code: ReceiptLinguaErrorCode;
  public readonly details: Record<string, unknown>;

  constructor(
    code: ReceiptLinguaErrorCode,
    message: string,
    details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ReceiptLinguaError";
    this.code = code;
    this.details = details;
    // Restore prototype chain when compiled down (Node/TS class-extends-Error quirk).
    Object.setPrototypeOf(this, ReceiptLinguaError.prototype);
  }
}

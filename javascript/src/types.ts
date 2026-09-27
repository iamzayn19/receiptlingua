/**
 * Hand-written TypeScript types mirroring `protocol/schema/response.schema.json`
 * and `protocol/schema/error.schema.json`.
 *
 * Why hand-written rather than codegen'd (e.g. via `json-schema-to-typescript`):
 * the schemas use `$ref`/`$defs` with a handful of shared shapes (scalar_field,
 * bbox, polygon, evidence) that are reused across many properties. A generator
 * produces a workable but verbose/duplicated result for this shape without
 * extra config; hand-writing once and keeping the two files next to each other
 * (both read during this milestone) is precise and easy to keep in sync given
 * how rarely the protocol version bumps. If the schema grows materially, revisit
 * `json-schema-to-typescript` rather than hand-maintaining a big diff.
 */

/** BCP 47 language tag, e.g. "en", "ta", "ar". */
export type LanguageCode = string;

/** ISO 15924 four-letter script code, e.g. "Latn", "Taml", "Arab". */
export type ScriptCode = string;

export type ProcessingMode = "fast" | "accurate" | "auto";

export type FieldStatus = "ok" | "inferred_field" | "uncertain" | "missing";

export type RecognitionStatus = "ok" | "illegible" | "truncated" | "missing_region" | "uncertain";

/** Stable machine-readable error codes from `protocol/schema/error.schema.json`. */
export type ReceiptLinguaErrorCode =
  | "INVALID_IMAGE"
  | "UNSUPPORTED_FORMAT"
  | "MODEL_NOT_FOUND"
  | "MODEL_DOWNLOAD_FAILED"
  | "OCR_FAILED"
  | "OUT_OF_MEMORY"
  | "UNSUPPORTED_BACKEND"
  | "INVALID_CONFIGURATION"
  /** Not part of the protocol vocabulary: raised locally when the Python
   * `receiptlingua` CLI itself cannot be found/invoked (missing Python,
   * missing package, etc). Kept in the same union so callers can switch
   * on `.code` uniformly. */
  | "CLI_NOT_FOUND"
  /** Local-only: the CLI ran but its stdout was not parseable JSON, or
   * did not match the expected envelope shape. */
  | "PROTOCOL_ERROR";

export interface Evidence {
  text_line_indices?: number[];
  word_indices?: number[];
}

export interface ScalarField<T = unknown> {
  value?: T;
  status: FieldStatus;
  confidence?: number;
  evidence?: Evidence;
}

export interface LineItem {
  description?: ScalarField<string>;
  quantity?: ScalarField<number>;
  unit_price?: ScalarField<number>;
  item_total?: ScalarField<number>;
  status: FieldStatus;
  evidence?: Evidence;
}

export interface StructuredFields {
  merchant?: ScalarField<string>;
  merchant_address?: ScalarField<string>;
  date?: ScalarField<string>;
  time?: ScalarField<string>;
  currency?: ScalarField<string>;
  subtotal?: ScalarField<number>;
  tax?: ScalarField<number>;
  discounts?: ScalarField<number>;
  total?: ScalarField<number>;
  payment_method?: ScalarField<string>;
  receipt_number?: ScalarField<string>;
  line_items?: LineItem[];
}

export type Point = [number, number];

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Language {
  code: LanguageCode;
  confidence: number;
}

export interface TextLine {
  text: string;
  bbox: BoundingBox;
  polygon?: Point[];
  confidence: number;
  language?: LanguageCode;
  script?: ScriptCode;
  status: RecognitionStatus;
}

export interface Word {
  text: string;
  bbox: BoundingBox;
  polygon?: Point[];
  confidence: number;
  language?: LanguageCode;
  script?: ScriptCode;
  status: RecognitionStatus;
  line_index?: number;
}

export interface ImageMetadata {
  width: number;
  height: number;
  format: string;
  exif_orientation?: number;
}

/** The full OCR response envelope, matching `response.schema.json`. */
export interface ReceiptResult {
  schema_version: string;
  engine: string;
  engine_version: string;
  mode: ProcessingMode;
  image: ImageMetadata;
  processing_time_ms: number;
  languages: Language[];
  scripts: ScriptCode[];
  full_text: string;
  text_lines: TextLine[];
  words?: Word[];
  warnings: string[];
  fields: StructuredFields;
}

/** The error envelope, matching `error.schema.json`. */
export interface ReceiptErrorEnvelope {
  schema_version: string;
  error: {
    code: ReceiptLinguaErrorCode;
    message: string;
    details?: Record<string, unknown>;
  };
}

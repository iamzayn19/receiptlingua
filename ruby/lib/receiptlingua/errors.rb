# frozen_string_literal: true

module ReceiptLingua
  # Error type for every failure this client can raise, whether it came from
  # the Python sidecar's own error envelope (protocol/schema/error.schema.json)
  # or from a local problem invoking it (missing interpreter, malformed
  # output). Callers should branch on #code, not on #message -- message text
  # may change between versions, per the protocol's own doc comment on
  # "message". Mirrors javascript/src/errors.ts's ReceiptLinguaError.
  class Error < StandardError
    # Machine-readable codes drawn from protocol/schema/error.schema.json's
    # enum, plus two client-local codes that are not part of the protocol.
    CODES = %w[
      INVALID_IMAGE
      UNSUPPORTED_FORMAT
      MODEL_NOT_FOUND
      MODEL_DOWNLOAD_FAILED
      OCR_FAILED
      OUT_OF_MEMORY
      UNSUPPORTED_BACKEND
      INVALID_CONFIGURATION
      CLI_NOT_FOUND
      PROTOCOL_ERROR
    ].freeze

    attr_reader :code, :details

    def initialize(code, message, details = {})
      @code = code
      @details = details
      super(message)
    end
  end

  # Raised locally when the Python `receiptlingua` CLI itself cannot be
  # found or run (missing Python, missing package, wrong path, etc), as
  # opposed to CLI_NOT_FOUND cases that Error already covers generically.
  # Kept as a distinct class so `rescue ReceiptLingua::CliNotFoundError`
  # reads naturally, while still being a ReceiptLingua::Error with
  # code == "CLI_NOT_FOUND" for callers that switch on #code.
  class CliNotFoundError < Error
    def initialize(message, details = {})
      super("CLI_NOT_FOUND", message, details)
    end
  end

  # Raised when the CLI ran but produced output that either isn't valid
  # JSON, or is valid JSON that doesn't match the expected response/error
  # envelope shape.
  class ProtocolError < Error
    def initialize(message, details = {})
      super("PROTOCOL_ERROR", message, details)
    end
  end
end

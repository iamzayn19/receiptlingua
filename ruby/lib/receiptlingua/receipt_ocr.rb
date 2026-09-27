# frozen_string_literal: true

require "json"
require "open3"

require_relative "errors"
require_relative "types"

module ReceiptLingua
  # Thin Ruby client for the ReceiptLingua OCR engine.
  #
  # Transport note (see ARCHITECTURE.md / protocol/README.md): the real
  # sidecar transport (stdio or a local socket, with its own framing) is an
  # open ADR item and has not been built yet. As a stopgap -- mirroring
  # javascript/src/receipt-ocr.ts's identical decision -- this client shells
  # out to the already-working Python `receiptlingua` CLI (`scan --json`) as
  # a fresh subprocess *per call*. This is correct and fully
  # protocol-conformant, but it is NOT the final transport: every #scan call
  # pays the full Python/model-load startup cost, because nothing is kept
  # warm between calls. A persistent sidecar daemon is the documented next
  # step for whoever picks up that ADR; the Ruby and JS clients face the
  # identical question and neither should invent its own answer ahead of it.
  class ReceiptOCR
    DEFAULT_CLI_COMMAND = ["receiptlingua"].freeze
    REQUIRED_RESULT_KEYS = %w[
      schema_version engine engine_version mode image processing_time_ms
      languages scripts full_text text_lines warnings fields
    ].freeze

    # @param cli_command [Array<String>] Full command used to invoke the
    #   Python CLI, as argv (program + leading args). Defaults to
    #   ["receiptlingua"], the console script installed by
    #   `pip install receiptlingua`, resolved via PATH. Override to point at
    #   a specific interpreter/venv, e.g.
    #   ["/path/to/venv/bin/python", "-m", "receiptlingua.cli"].
    # @param mode [String] Processing mode passed through to `--mode`
    #   ("fast", "accurate", or "auto").
    # @param languages [Array<String>] Language codes passed through to
    #   `--lang` as a comma-joined list.
    # @param cache_dir [String] Sets RECEIPTLINGUA_CACHE_DIR for the
    #   subprocess, matching the Python CacheManager.from_env() lookup order
    #   (python/src/receiptlingua/engines/cache.py).
    # @param timeout [Numeric] Kill the subprocess and raise if it runs
    #   longer than this many seconds. Default: none.
    def initialize(cli_command: nil, mode: nil, languages: nil, cache_dir: nil, timeout: nil)
      @cli_command = cli_command || DEFAULT_CLI_COMMAND
      @mode = mode
      @languages = languages
      @cache_dir = cache_dir
      @timeout = timeout
    end

    # Runs OCR + field extraction on a receipt image.
    #
    # @param path [String] Path to an image file.
    # @param mode [String] Overrides the mode set on the client for this call.
    # @param languages [Array<String>] Overrides the languages set on the
    #   client for this call.
    # @return [ReceiptLingua::Types::Result]
    # @raise [ReceiptLingua::Error] on any protocol-level or local failure.
    def scan(path, mode: nil, languages: nil)
      program, *leading_args = @cli_command
      args = leading_args + build_scan_args(path, mode, languages)

      stdout, stderr, status = run(program, args, build_env)

      raise error_from_failure(stdout, stderr, status) if status.nil? || !status.success?

      parse_result(stdout)
    end

    private

    def build_scan_args(path, mode, languages)
      effective_mode = mode || @mode
      effective_languages = languages || @languages

      args = ["scan", path, "--json"]
      args += ["--mode", effective_mode] if effective_mode
      args += ["--lang", Array(effective_languages).join(",")] if effective_languages && !effective_languages.empty?
      args
    end

    def build_env
      env = {}
      env["RECEIPTLINGUA_CACHE_DIR"] = @cache_dir if @cache_dir
      env
    end

    def run(program, args, env)
      opts = { binmode: true }
      if @timeout
        run_with_timeout(program, args, env, opts)
      else
        Open3.capture3(env, program, *args, **opts)
      end
    rescue Errno::ENOENT => e
      raise spawn_error_to_receiptlingua_error(e, program)
    end

    def run_with_timeout(program, args, env, opts)
      stdout = +""
      stderr = +""
      status = nil
      Open3.popen3(env, program, *args, **opts) do |stdin, stdout_io, stderr_io, wait_thr|
        stdin.close
        unless wait_thr.join(@timeout)
          Process.kill("TERM", wait_thr.pid) if wait_thr.alive?
          raise Error.new(
            "OCR_FAILED",
            "receiptlingua CLI timed out after #{@timeout}s",
            { program: program, args: args }
          )
        end
        stdout = stdout_io.read
        stderr = stderr_io.read
        status = wait_thr.value
      end
      [stdout, stderr, status]
    end

    def spawn_error_to_receiptlingua_error(err, program)
      CliNotFoundError.new(
        "Could not find or run \"#{program}\". The ReceiptLingua Python engine must be " \
        "installed and on PATH (`pip install receiptlingua`), or pass an explicit " \
        "cli_command: to ReceiptLingua::ReceiptOCR.new pointing at the interpreter/venv " \
        "to use, e.g. ReceiptLingua::ReceiptOCR.new(cli_command: " \
        "[\"/path/to/venv/bin/python\", \"-m\", \"receiptlingua.cli\"]).",
        { program: program, original_message: err.message }
      )
    end

    def error_from_failure(stdout, stderr, status)
      candidate = stdout.nil? || stdout.strip.empty? ? stderr : stdout
      parsed = try_parse_json(candidate)
      error_envelope_to_error(parsed) || generic_ocr_failed_error(stdout, stderr, status)
    end

    def error_envelope_to_error(parsed)
      return nil unless parsed && error_envelope?(parsed)

      error = parsed["error"]
      Error.new(error["code"], error["message"], error["details"] || {})
    end

    def generic_ocr_failed_error(stdout, stderr, status)
      exit_code = status&.exitstatus
      output = stderr.to_s.strip.empty? ? stdout.to_s.strip : stderr.to_s.strip
      output = "(no output)" if output.empty?
      Error.new(
        "OCR_FAILED",
        "receiptlingua CLI exited with code #{exit_code.inspect}: #{output}",
        { exit_code: exit_code, stderr: stderr.to_s.strip, stdout: stdout.to_s.strip }
      )
    end

    def parse_result(stdout)
      parsed = try_parse_json(stdout)
      if parsed.nil?
        raise ProtocolError.new(
          "receiptlingua CLI produced output that was not valid JSON.",
          { stdout: stdout.to_s[0, 2000] }
        )
      end
      if error_envelope?(parsed)
        error = parsed["error"]
        raise Error.new(error["code"], error["message"], error["details"] || {})
      end
      unless result_envelope?(parsed)
        raise ProtocolError.new(
          "receiptlingua CLI produced JSON that does not match the expected response shape.",
          { received: parsed }
        )
      end
      Types::Builder.build_result(parsed)
    end

    def try_parse_json(text)
      return nil if text.nil?

      JSON.parse(text)
    rescue JSON::ParserError
      nil
    end

    def error_envelope?(value)
      value.is_a?(Hash) && value["error"].is_a?(Hash) && value["error"]["code"].is_a?(String)
    end

    def result_envelope?(value)
      value.is_a?(Hash) && REQUIRED_RESULT_KEYS.all? { |k| value.key?(k) }
    end
  end
end

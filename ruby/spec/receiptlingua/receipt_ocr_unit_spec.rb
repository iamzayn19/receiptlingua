# frozen_string_literal: true

require "spec_helper"
require "open3"

RSpec.describe ReceiptLingua::ReceiptOCR do
  let(:valid_result) do
    {
      "schema_version" => "0.1.0",
      "engine" => "tesseract",
      "engine_version" => "5.5.2",
      "mode" => "auto",
      "image" => { "width" => 10, "height" => 10, "format" => "png" },
      "processing_time_ms" => 12.3,
      "languages" => [{ "code" => "en", "confidence" => 0.9 }],
      "scripts" => ["Latn"],
      "full_text" => "HELLO",
      "text_lines" => [],
      "warnings" => [],
      "fields" => {}
    }
  end

  def status_double(success:, exitstatus:)
    instance_double(Process::Status, success?: success, exitstatus: exitstatus)
  end

  describe "#scan (mocked subprocess)" do
    it "parses a successful JSON response into a Types::Result" do
      allow(Open3).to receive(:capture3)
        .and_return([JSON.generate(valid_result), "", status_double(success: true, exitstatus: 0)])

      ocr = described_class.new
      result = ocr.scan("/tmp/whatever.png")

      expect(result).to be_a(ReceiptLingua::Types::Result)
      expect(result.full_text).to eq("HELLO")
      expect(result.engine).to eq("tesseract")
      expect(result.languages.first.code).to eq("en")

      expect(Open3).to have_received(:capture3) do |env, program, *args|
        expect(env).to eq({})
        expect(program).to eq("receiptlingua")
        expect(args).to include("scan", "/tmp/whatever.png", "--json")
      end
    end

    it "passes mode and languages through to the CLI args" do
      allow(Open3).to receive(:capture3)
        .and_return([JSON.generate(valid_result), "", status_double(success: true, exitstatus: 0)])

      ocr = described_class.new(mode: "accurate", languages: %w[en ta])
      ocr.scan("/tmp/x.png")

      expect(Open3).to have_received(:capture3) do |_env, _program, *args|
        expect(args).to include("--mode", "accurate", "--lang", "en,ta")
      end
    end

    it "allows overriding mode/languages per call" do
      allow(Open3).to receive(:capture3)
        .and_return([JSON.generate(valid_result), "", status_double(success: true, exitstatus: 0)])

      ocr = described_class.new(mode: "accurate")
      ocr.scan("/tmp/x.png", mode: "fast", languages: ["ar"])

      expect(Open3).to have_received(:capture3) do |_env, _program, *args|
        expect(args).to include("--mode", "fast", "--lang", "ar")
      end
    end

    it "sets RECEIPTLINGUA_CACHE_DIR in the subprocess env when cache_dir is given" do
      allow(Open3).to receive(:capture3)
        .and_return([JSON.generate(valid_result), "", status_double(success: true, exitstatus: 0)])

      ocr = described_class.new(cache_dir: "/tmp/cache")
      ocr.scan("/tmp/x.png")

      expect(Open3).to have_received(:capture3) do |env, *_rest|
        expect(env["RECEIPTLINGUA_CACHE_DIR"]).to eq("/tmp/cache")
      end
    end

    it "maps a protocol error envelope (non-zero exit) to a matching Error" do
      envelope = {
        "schema_version" => "0.1.0",
        "error" => {
          "code" => "INVALID_IMAGE",
          "message" => "Invalid image: unreadable",
          "details" => { "reason" => "unreadable" }
        }
      }
      allow(Open3).to receive(:capture3)
        .and_return([JSON.generate(envelope), "", status_double(success: false, exitstatus: 1)])

      ocr = described_class.new
      expect { ocr.scan("/tmp/bad.png") }.to raise_error(ReceiptLingua::Error) do |error|
        expect(error.code).to eq("INVALID_IMAGE")
        expect(error.message).to eq("Invalid image: unreadable")
        expect(error.details["reason"]).to eq("unreadable")
      end
    end

    it "raises ProtocolError when stdout is not valid JSON" do
      allow(Open3).to receive(:capture3)
        .and_return(["not json at all", "", status_double(success: true, exitstatus: 0)])

      ocr = described_class.new
      expect { ocr.scan("/tmp/x.png") }.to raise_error(ReceiptLingua::ProtocolError) do |error|
        expect(error.code).to eq("PROTOCOL_ERROR")
      end
    end

    it "raises ProtocolError when JSON is valid but doesn't match the response shape" do
      allow(Open3).to receive(:capture3)
        .and_return([JSON.generate({ "unexpected" => true }), "", status_double(success: true, exitstatus: 0)])

      ocr = described_class.new
      expect { ocr.scan("/tmp/x.png") }.to raise_error(ReceiptLingua::ProtocolError)
    end

    it "raises OCR_FAILED with stderr context when exit is non-zero and output isn't an error envelope" do
      allow(Open3).to receive(:capture3)
        .and_return(["", "traceback: boom", status_double(success: false, exitstatus: 2)])

      ocr = described_class.new
      expect { ocr.scan("/tmp/x.png") }.to raise_error(ReceiptLingua::Error) do |error|
        expect(error.code).to eq("OCR_FAILED")
        expect(error.message).to include("boom")
      end
    end

    it "raises CliNotFoundError with an actionable message when spawn fails with ENOENT" do
      allow(Open3).to receive(:capture3).and_raise(Errno::ENOENT.new("No such file or directory - receiptlingua"))

      ocr = described_class.new
      expect { ocr.scan("/tmp/x.png") }.to raise_error(ReceiptLingua::CliNotFoundError) do |error|
        expect(error.code).to eq("CLI_NOT_FOUND")
        expect(error.message).to include("pip install receiptlingua")
      end
    end

    it "preserves non-ASCII UTF-8 text (Tamil, Arabic) through the stdout/JSON round trip" do
      # Real Tamil ("Vanakkam, ரசீது") and Arabic ("Fatura", invoice) text --
      # not just codepoints, since a naive Latin-1 fallback in Open3 or
      # JSON.parse would only be caught by real multi-byte UTF-8 characters,
      # not by e.g. accented Latin. This is the concrete risk the milestone
      # brief calls out: Ruby subprocess pipes are ASCII-8BIT by default
      # unless explicitly handled, and #run below passes binmode: true and
      # relies on JSON.parse re-tagging the string as UTF-8.
      tamil_text = "வணக்கம், ரசீது எண் ௧௨௩"
      arabic_text = "فاتورة الشراء رقم ١٢٣"
      multilingual_result = valid_result.merge(
        "full_text" => "#{tamil_text}\n#{arabic_text}",
        "languages" => [{ "code" => "ta", "confidence" => 0.8 }, { "code" => "ar", "confidence" => 0.7 }],
        "scripts" => %w[Taml Arab]
      )

      allow(Open3).to receive(:capture3)
        .and_return([JSON.generate(multilingual_result), "", status_double(success: true, exitstatus: 0)])

      ocr = described_class.new
      result = ocr.scan("/tmp/multilingual.png")

      expect(result.full_text.encoding).to eq(Encoding::UTF_8)
      expect(result.full_text).to be_valid_encoding
      expect(result.full_text).to include(tamil_text)
      expect(result.full_text).to include(arabic_text)
      expect(result.full_text.each_char.count { |c| c.ord > 127 }).to be > 0
    end

    it "uses a custom cli_command when provided" do
      allow(Open3).to receive(:capture3)
        .and_return([JSON.generate(valid_result), "", status_double(success: true, exitstatus: 0)])

      ocr = described_class.new(cli_command: ["/venv/bin/python", "-m", "receiptlingua.cli"])
      ocr.scan("/tmp/x.png")

      expect(Open3).to have_received(:capture3) do |_env, program, *args|
        expect(program).to eq("/venv/bin/python")
        expect(args[0..1]).to eq(["-m", "receiptlingua.cli"])
        expect(args).to include("scan")
      end
    end
  end
end

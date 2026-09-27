# frozen_string_literal: true

require "spec_helper"
require "open3"
require "tmpdir"
require "json"

# Real end-to-end test: shells out to the ACTUAL installed Python
# `receiptlingua` CLI (python/.venv/bin/receiptlingua if present, else
# whatever `receiptlingua` resolves to on PATH) against real synthetic
# fixtures from the Python test suite, asserting real, schema-shaped,
# non-empty results.
#
# Mirrors javascript/test/receipt-ocr.integration.test.ts's skip-if-missing
# pattern (which itself mirrors the Python suite's skip-on-missing-langpack
# pattern): if no working `receiptlingua` CLI is importable in whatever
# environment runs this, the test SKIPs rather than fails, since this repo's
# CI/dev environments may not always have the Python package installed.
RSpec.describe "ReceiptLingua::ReceiptOCR#scan (real Python CLI integration)" do
  ROOT = File.expand_path("../../..", __dir__)
  FIXTURES = File.join(ROOT, "python", "tests", "fixtures")
  ENG_FIXTURE = File.join(FIXTURES, "receipt_text_eng.png")
  TAM_FIXTURE = File.join(FIXTURES, "receipt_text_tam.png")

  def find_cli_command
    venv_bin = File.join(ROOT, "python", ".venv", "bin", "receiptlingua")
    if File.exist?(venv_bin)
      _out, _err, status = Open3.capture3(venv_bin, "--version")
      return [venv_bin] if status.success?
    end
    _out, _err, status = Open3.capture3("receiptlingua", "--version")
    return ["receiptlingua"] if status.success?

    nil
  rescue Errno::ENOENT
    nil
  end

  # Tamil/Arabic fixtures additionally require tam.traineddata/ara.traineddata
  # to be discoverable by Tesseract -- see
  # python/tests/test_tesseract_engine.py's identical skip-cleanly rationale.
  # Without it, Tesseract still runs (against the wrong/default langpack) and
  # returns *some* text, so we can't detect this case by an empty result; we
  # check `tesseract --list-langs` directly instead.
  def tesseract_lang_available?(code)
    out, _err, status = Open3.capture3("tesseract", "--list-langs")
    status.success? && out.split("\n").include?(code)
  rescue Errno::ENOENT
    false
  end

  before(:context) do
    @cli_command = find_cli_command
  end

  it "returns a real, schema-shaped, non-empty result for a synthetic fixture" do
    skip "no working `receiptlingua` CLI found (checked python/.venv/bin and PATH)" unless @cli_command
    expect(File.exist?(ENG_FIXTURE)).to be(true)

    ocr = ReceiptLingua::ReceiptOCR.new(cli_command: @cli_command)
    result = ocr.scan(ENG_FIXTURE)

    expect(result.schema_version).to match(/\A\d+\.\d+\.\d+\z/)
    expect(result.engine).to be_a(String)
    expect(result.engine).not_to be_empty
    expect(%w[fast accurate auto]).to include(result.mode)
    expect(result.image.width).to be > 0
    expect(result.image.height).to be > 0
    expect(result.text_lines).to be_an(Array)
    expect(result.languages).to be_an(Array)
    expect(result.full_text).to be_a(String)
    expect(result.full_text.strip.length).to be > 0
    expect(result.fields).to be_a(ReceiptLingua::Types::StructuredFields)
  end

  it "raises a typed Error for a nonexistent path via the real CLI" do
    skip "no working `receiptlingua` CLI found (checked python/.venv/bin and PATH)" unless @cli_command

    ocr = ReceiptLingua::ReceiptOCR.new(cli_command: @cli_command)
    expect { ocr.scan("/definitely/does/not/exist.png") }.to raise_error(ReceiptLingua::Error) do |error|
      expect(error.code).to eq("INVALID_IMAGE")
    end
  end

  it "preserves non-ASCII UTF-8 bytes through a REAL (unmocked) subprocess pipe" do
    # Unlike the mocked unit spec (which only proves JSON.parse handles
    # UTF-8 once a Ruby string already has the bytes), this drives a real
    # child process via Open3 so the actual pipe/encoding path -- the one
    # historically prone to Ruby ASCII-8BIT-vs-UTF-8 bugs -- is exercised
    # for real, without needing Tesseract's Tamil/Arabic langpacks.
    tamil_text = "வணக்கம் ரசீது"
    fake_response = {
      "schema_version" => "0.1.0", "engine" => "fake", "engine_version" => "0",
      "mode" => "auto", "image" => { "width" => 1, "height" => 1, "format" => "png" },
      "processing_time_ms" => 0, "languages" => [], "scripts" => ["Taml"],
      "full_text" => tamil_text, "text_lines" => [], "warnings" => [], "fields" => {}
    }
    Dir.mktmpdir do |dir|
      script = File.join(dir, "fake_cli.rb")
      File.write(script, <<~RUBY, encoding: "UTF-8")
        STDOUT.set_encoding("UTF-8")
        puts #{fake_response.to_json.dump}
      RUBY

      ocr = ReceiptLingua::ReceiptOCR.new(cli_command: [RbConfig.ruby, script])
      result = ocr.scan("unused.png")

      expect(result.full_text.encoding).to eq(Encoding::UTF_8)
      expect(result.full_text).to eq(tamil_text)
      expect(result.full_text.each_char.any? { |c| c.ord > 127 }).to be(true)
    end
  end

  it "preserves UTF-8 non-ASCII (Tamil) text through the subprocess/JSON round trip" do
    skip "no working `receiptlingua` CLI found (checked python/.venv/bin and PATH)" unless @cli_command
    skip "Tamil fixture not present" unless File.exist?(TAM_FIXTURE)
    skip "tam.traineddata not discoverable by tesseract in this environment" unless tesseract_lang_available?("tam")

    ocr = ReceiptLingua::ReceiptOCR.new(cli_command: @cli_command)
    result = ocr.scan(TAM_FIXTURE)

    expect(result.full_text.encoding).to eq(Encoding::UTF_8)
    expect(result.full_text).to be_valid_encoding
    # The Tamil script uses codepoints outside the ASCII range; a mangled
    # (e.g. Latin-1-misdecoded or double-encoded) round trip would either
    # raise on invalid encoding above, or every character would collapse
    # into the ASCII range. Assert we really got non-ASCII bytes through.
    expect(result.full_text.each_char.any? { |c| c.ord > 127 }).to be(true)
  end
end

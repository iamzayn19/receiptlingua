# frozen_string_literal: true

require_relative "lib/receiptlingua/version"

Gem::Specification.new do |spec|
  spec.name = "receiptlingua"
  spec.version = ReceiptLingua::VERSION
  spec.authors = ["iamzayn19"]
  spec.email = ["iamzayn19@gmail.com"]

  spec.summary = "Offline-first, multilingual receipt OCR (Ruby client for the receiptlingua Python engine)"
  spec.description = <<~DESC
    Ruby client for ReceiptLingua, an offline-first multilingual receipt OCR
    engine. This gem shells out to the Python `receiptlingua` CLI
    (`scan --json`) as a subprocess per call -- a documented stopgap ahead of
    a future sidecar-daemon transport -- and parses its output into typed
    Ruby result objects and errors matching the ReceiptLingua wire protocol.
  DESC
  spec.homepage = "https://github.com/iamzayn19/receiptlingua"
  spec.license = "Apache-2.0"
  spec.required_ruby_version = ">= 3.0"

  spec.metadata["homepage_uri"] = spec.homepage
  spec.metadata["source_code_uri"] = "#{spec.homepage}/tree/main/ruby"
  spec.metadata["changelog_uri"] = "#{spec.homepage}/blob/main/docs/COMMIT_PLAN.md"
  spec.metadata["rubygems_mfa_required"] = "true"

  spec.files = Dir.chdir(__dir__) do
    `git ls-files -z`.split("\x0").select do |f|
      (f == __FILE__) || f.match(%r{\A(?:lib)/}) || f == "README.md" || f == "LICENSE"
    end
  end
  spec.bindir = "exe"
  spec.executables = spec.files.grep(%r{\Aexe/}) { |f| File.basename(f) }
  spec.require_paths = ["lib"]

  spec.add_development_dependency "rspec", "~> 3.13"
  spec.add_development_dependency "rubocop", "~> 1.65"
end

# frozen_string_literal: true

module ReceiptLingua
  # Value objects mirroring protocol/schema/response.schema.json, built by
  # hand rather than codegen'd -- same rationale as javascript/src/types.ts:
  # the schema's $ref/$defs reuse (scalar_field, bbox, polygon, evidence) is
  # small and stable enough that hand-writing once, next to the schema, is
  # more precise than tuning a generator for this shape.
  #
  # Each type is a plain Struct built from the CLI's parsed JSON (string
  # keys); unset optional fields come through as nil rather than being
  # omitted from the Struct, which keeps every accessor always callable.
  module Types
    BoundingBox = Struct.new(:x, :y, :width, :height, keyword_init: true)
    Language = Struct.new(:code, :confidence, keyword_init: true)
    Evidence = Struct.new(:text_line_indices, :word_indices, keyword_init: true)
    ImageMetadata = Struct.new(:width, :height, :format, :exif_orientation, keyword_init: true)

    ScalarField = Struct.new(:value, :status, :confidence, :evidence, keyword_init: true)

    LineItem = Struct.new(
      :description, :quantity, :unit_price, :item_total, :status, :evidence,
      keyword_init: true
    )

    StructuredFields = Struct.new(
      :merchant, :merchant_address, :date, :time, :currency, :subtotal, :tax,
      :discounts, :total, :payment_method, :receipt_number, :line_items,
      keyword_init: true
    )

    TextLine = Struct.new(
      :text, :bbox, :polygon, :confidence, :language, :script, :status,
      keyword_init: true
    )

    Word = Struct.new(
      :text, :bbox, :polygon, :confidence, :language, :script, :status, :line_index,
      keyword_init: true
    )

    # The full OCR response envelope, matching response.schema.json.
    Result = Struct.new(
      :schema_version, :engine, :engine_version, :mode, :image,
      :processing_time_ms, :languages, :scripts, :full_text, :text_lines,
      :words, :warnings, :fields,
      keyword_init: true
    )

    # Builds the typed Struct tree above from a Hash parsed from the CLI's
    # JSON output (string keys, as Ruby's JSON.parse returns by default).
    module Builder
      module_function

      def build_result(hash)
        Result.new(
          schema_version: hash["schema_version"],
          engine: hash["engine"],
          engine_version: hash["engine_version"],
          mode: hash["mode"],
          image: build_image(hash["image"]),
          processing_time_ms: hash["processing_time_ms"],
          languages: Array(hash["languages"]).map { |l| build_language(l) },
          scripts: Array(hash["scripts"]),
          full_text: hash["full_text"],
          text_lines: Array(hash["text_lines"]).map { |l| build_text_line(l) },
          words: hash["words"] && Array(hash["words"]).map { |w| build_word(w) },
          warnings: Array(hash["warnings"]),
          fields: build_structured_fields(hash["fields"])
        )
      end

      def build_image(hash)
        return nil unless hash

        ImageMetadata.new(
          width: hash["width"],
          height: hash["height"],
          format: hash["format"],
          exif_orientation: hash["exif_orientation"]
        )
      end

      def build_language(hash)
        Language.new(code: hash["code"], confidence: hash["confidence"])
      end

      def build_bbox(hash)
        return nil unless hash

        BoundingBox.new(x: hash["x"], y: hash["y"], width: hash["width"], height: hash["height"])
      end

      def build_evidence(hash)
        return nil unless hash

        Evidence.new(
          text_line_indices: hash["text_line_indices"],
          word_indices: hash["word_indices"]
        )
      end

      def build_text_line(hash)
        TextLine.new(
          text: hash["text"],
          bbox: build_bbox(hash["bbox"]),
          polygon: hash["polygon"],
          confidence: hash["confidence"],
          language: hash["language"],
          script: hash["script"],
          status: hash["status"]
        )
      end

      def build_word(hash)
        Word.new(
          text: hash["text"],
          bbox: build_bbox(hash["bbox"]),
          polygon: hash["polygon"],
          confidence: hash["confidence"],
          language: hash["language"],
          script: hash["script"],
          status: hash["status"],
          line_index: hash["line_index"]
        )
      end

      def build_scalar_field(hash)
        return nil unless hash

        ScalarField.new(
          value: hash["value"],
          status: hash["status"],
          confidence: hash["confidence"],
          evidence: build_evidence(hash["evidence"])
        )
      end

      def build_line_item(hash)
        LineItem.new(
          description: build_scalar_field(hash["description"]),
          quantity: build_scalar_field(hash["quantity"]),
          unit_price: build_scalar_field(hash["unit_price"]),
          item_total: build_scalar_field(hash["item_total"]),
          status: hash["status"],
          evidence: build_evidence(hash["evidence"])
        )
      end

      def build_structured_fields(hash)
        hash ||= {}
        StructuredFields.new(
          merchant: build_scalar_field(hash["merchant"]),
          merchant_address: build_scalar_field(hash["merchant_address"]),
          date: build_scalar_field(hash["date"]),
          time: build_scalar_field(hash["time"]),
          currency: build_scalar_field(hash["currency"]),
          subtotal: build_scalar_field(hash["subtotal"]),
          tax: build_scalar_field(hash["tax"]),
          discounts: build_scalar_field(hash["discounts"]),
          total: build_scalar_field(hash["total"]),
          payment_method: build_scalar_field(hash["payment_method"]),
          receipt_number: build_scalar_field(hash["receipt_number"]),
          line_items: hash["line_items"] && Array(hash["line_items"]).map { |li| build_line_item(li) }
        )
      end
    end
  end
end

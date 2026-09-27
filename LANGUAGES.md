# Language support matrix

This file is generated from
[`python/src/receiptlingua/langid/data/language_matrix.json`](python/src/receiptlingua/langid/data/language_matrix.json)
by `python/scripts/generate_languages_md.py`. Edit the JSON, then re-run
that script -- don't hand-edit the table below, it will be overwritten.

## Two separate concepts (read this before the table)

This project tracks two deliberately different things per language, and
they must never be conflated:

- **`model_supported`**: the backend stack can *technically* produce
  output for this language right now. This is checked against real,
  verified capability: does [py3langid](https://pypi.org/project/py3langid/)'s
  bundled language ID model have a label for it, **and** does
  [Tesseract](https://github.com/tesseract-ocr/tessdata_fast) have a
  documented trained-data language pack for it. Both must be true.
- **`receipt_verified`**: there is real benchmark evidence this
  language/script combination works well specifically *on receipts*
  (thermal-printer fonts, low-quality photos, receipt layouts) -- not
  just on the general-purpose text these backends/models were originally
  trained on.

**As of this milestone (81-100), there is no receipt benchmark yet**
(that is a later milestone, 171-185). So every single row below has
`receipt_verified = false`, honestly, regardless of how well-supported
the language otherwise looks. A `true` here will only ever appear once a
real benchmark has produced real evidence -- never as a placeholder or
aspiration.

## Coverage summary


- **87 / 94** entries are `model_supported = true` right now.
- **32 / 32** of the project's mandatory high-priority languages are `model_supported = true` (all of them, as of this milestone -- see notes below on why the *rest* of the 94 aren't).
- **0 / 94** are `receipt_verified = true` (expected: zero, no receipt benchmark exists yet).

The gap between `model_supported` and the aspirational ~109-language target is **not a hard ceiling** -- it reflects which Tesseract language packs (`.traineddata` files) are actually installed in a given checkout right now (only `eng` ships by default in this environment) versus which ones Tesseract's `tessdata_fast` distribution documents as available. Installing more packs (`brew install tesseract-lang` for the full set, or fetching individual `.traineddata` files) is a coverage-expansion task for later, not something blocked on code here. A handful of entries are marked `model_supported = false` for a *different*, real reason: py3langid's 142-label model has no language ID label for them (e.g. Tibetan, Dhivehi, Tigrinya) or no Tesseract pack exists for them at all -- see each row's notes.

## Mandatory high-priority languages

| Code | Name | Script | RTL | Model supported | Receipt verified | Notes |
|---|---|---|---|---|---|---|
| `en` | English | Latn | No | Yes | No | Tesseract langpack 'eng' installed locally. py3langid label 'en'. |
| `ur` | Urdu | Arab | Yes | Yes | No | Tesseract tessdata_fast langpack 'urd' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'ur'. |
| `ar` | Arabic | Arab | Yes | Yes | No | Tesseract tessdata_fast langpack 'ara' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'ar'. |
| `hi` | Hindi | Deva | No | Yes | No | Tesseract tessdata_fast langpack 'hin' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'hi'. |
| `ta` | Tamil | Taml | No | Yes | No | Tesseract tessdata_fast langpack 'tam' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'ta'. |
| `te` | Telugu | Telu | No | Yes | No | Tesseract tessdata_fast langpack 'tel' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'te'. |
| `bn` | Bengali | Beng | No | Yes | No | Tesseract tessdata_fast langpack 'ben' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'bn'. |
| `pa` | Punjabi | Guru | No | Yes | No | Tesseract tessdata_fast langpack 'pan' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'pa'. |
| `gu` | Gujarati | Gujr | No | Yes | No | Tesseract tessdata_fast langpack 'guj' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'gu'. |
| `kn` | Kannada | Knda | No | Yes | No | Tesseract tessdata_fast langpack 'kan' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'kn'. |
| `ml` | Malayalam | Mlym | No | Yes | No | Tesseract tessdata_fast langpack 'mal' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'ml'. |
| `mr` | Marathi | Deva | No | Yes | No | Tesseract tessdata_fast langpack 'mar' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'mr'. |
| `ne` | Nepali | Deva | No | Yes | No | Tesseract tessdata_fast langpack 'nep' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'ne'. |
| `fa` | Persian | Arab | Yes | Yes | No | Tesseract tessdata_fast langpack 'fas' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'fa'. |
| `zh-Hans` | Chinese (Simplified) | Hani | No | Yes | No | Tesseract tessdata_fast langpack 'chi_sim' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'zh'. py3langid only outputs a single generic 'zh' label and does not distinguish Simplified/Traditional; script/variant must come from the OCR backend's language pack choice, not language ID. |
| `zh-Hant` | Chinese (Traditional) | Hani | No | Yes | No | Tesseract tessdata_fast langpack 'chi_tra' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'zh'. py3langid only outputs a single generic 'zh' label and does not distinguish Simplified/Traditional; script/variant must come from the OCR backend's language pack choice, not language ID. |
| `ja` | Japanese | Jpan | No | Yes | No | Tesseract tessdata_fast langpack 'jpn' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'ja'. |
| `ko` | Korean | Hang | No | Yes | No | Tesseract tessdata_fast langpack 'kor' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'ko'. |
| `th` | Thai | Thai | No | Yes | No | Tesseract tessdata_fast langpack 'tha' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'th'. |
| `id` | Indonesian | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'ind' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'id'. |
| `ms` | Malay | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'msa' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'ms'. |
| `vi` | Vietnamese | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'vie' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'vi'. |
| `fr` | French | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'fra' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'fr'. |
| `de` | German | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'deu' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'de'. |
| `es` | Spanish | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'spa' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'es'. |
| `pt` | Portuguese | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'por' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'pt'. |
| `it` | Italian | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'ita' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'it'. |
| `nl` | Dutch | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'nld' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'nl'. |
| `tr` | Turkish | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'tur' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'tr'. |
| `ru` | Russian | Cyrl | No | Yes | No | Tesseract tessdata_fast langpack 'rus' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'ru'. |
| `uk` | Ukrainian | Cyrl | No | Yes | No | Tesseract tessdata_fast langpack 'ukr' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'uk'. |
| `pl` | Polish | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'pol' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'pl'. |

## Additional languages

| Code | Name | Script | RTL | Model supported | Receipt verified | Notes |
|---|---|---|---|---|---|---|
| `af` | Afrikaans | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'afr' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'af'. |
| `sq` | Albanian | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'sqi' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'sq'. |
| `am` | Amharic | Ethi | No | Yes | No | Tesseract tessdata_fast langpack 'amh' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'am'. |
| `hy` | Armenian | Armn | No | Yes | No | Tesseract tessdata_fast langpack 'hye' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'hy'. |
| `az` | Azerbaijani | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'aze' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'az'. |
| `eu` | Basque | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'eus' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'eu'. |
| `be` | Belarusian | Cyrl | No | Yes | No | Tesseract tessdata_fast langpack 'bel' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'be'. |
| `bs` | Bosnian | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'bos' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'bs'. |
| `bg` | Bulgarian | Cyrl | No | Yes | No | Tesseract tessdata_fast langpack 'bul' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'bg'. |
| `my` | Burmese | Mymr | No | Yes | No | Tesseract tessdata_fast langpack 'mya' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'my'. |
| `ca` | Catalan | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'cat' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'ca'. |
| `hr` | Croatian | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'hrv' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'hr'. |
| `cs` | Czech | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'ces' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'cs'. |
| `da` | Danish | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'dan' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'da'. |
| `et` | Estonian | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'est' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'et'. |
| `fi` | Finnish | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'fin' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'fi'. |
| `gl` | Galician | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'glg' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'gl'. |
| `ka` | Georgian | Geor | No | Yes | No | Tesseract tessdata_fast langpack 'kat' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'ka'. |
| `el` | Greek | Grek | No | Yes | No | Tesseract tessdata_fast langpack 'ell' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'el'. |
| `he` | Hebrew | Hebr | Yes | Yes | No | Tesseract tessdata_fast langpack 'heb' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'he'. |
| `hu` | Hungarian | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'hun' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'hu'. |
| `is` | Icelandic | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'isl' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'is'. |
| `ga` | Irish | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'gle' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'ga'. |
| `jv` | Javanese | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'jav' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'jv'. |
| `kk` | Kazakh | Cyrl | No | Yes | No | Tesseract tessdata_fast langpack 'kaz' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'kk'. |
| `km` | Khmer | Khmr | No | Yes | No | Tesseract tessdata_fast langpack 'khm' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'km'. |
| `ky` | Kyrgyz | Cyrl | No | Yes | No | Tesseract tessdata_fast langpack 'kir' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'ky'. |
| `lo` | Lao | Laoo | No | Yes | No | Tesseract tessdata_fast langpack 'lao' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'lo'. |
| `lv` | Latvian | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'lav' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'lv'. |
| `lt` | Lithuanian | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'lit' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'lt'. |
| `mk` | Macedonian | Cyrl | No | Yes | No | Tesseract tessdata_fast langpack 'mkd' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'mk'. |
| `mt` | Maltese | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'mlt' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'mt'. |
| `mn` | Mongolian | Cyrl | No | Yes | No | Tesseract tessdata_fast langpack 'mon' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'mn'. |
| `no` | Norwegian | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'nor' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'no'. |
| `or` | Odia | Orya | No | Yes | No | Tesseract tessdata_fast langpack 'ori' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'or'. |
| `ps` | Pashto | Arab | Yes | Yes | No | Tesseract tessdata_fast langpack 'pus' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'ps'. |
| `ro` | Romanian | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'ron' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'ro'. |
| `sa` | Sanskrit | Deva | No | Yes | No | Tesseract tessdata_fast langpack 'san' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'sa'. |
| `sr` | Serbian | Cyrl | No | Yes | No | Tesseract tessdata_fast langpack 'srp' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'sr'. |
| `si` | Sinhala | Sinh | No | Yes | No | Tesseract tessdata_fast langpack 'sin' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'si'. |
| `sk` | Slovak | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'slk' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'sk'. |
| `sl` | Slovenian | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'slv' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'sl'. |
| `sw` | Swahili | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'swa' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'sw'. |
| `sv` | Swedish | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'swe' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'sv'. |
| `tl` | Tagalog | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'tgl' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'tl'. |
| `tg` | Tajik | Cyrl | No | Yes | No | Tesseract tessdata_fast langpack 'tgk' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'tg'. |
| `tt` | Tatar | Cyrl | No | Yes | No | Tesseract tessdata_fast langpack 'tat' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'tt'. |
| `ug` | Uyghur | Arab | Yes | Yes | No | Tesseract tessdata_fast langpack 'uig' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'ug'. |
| `uz` | Uzbek | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'uzb' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'uz'. |
| `cy` | Welsh | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'cym' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'cy'. |
| `yo` | Yoruba | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'yor' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'yo'. |
| `zu` | Zulu | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'zul' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'zu'. |
| `as` | Assamese | Beng | No | Yes | No | Tesseract tessdata_fast langpack 'asm' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'as'. |
| `qu` | Quechua | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'que' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'qu'. |
| `ht` | Haitian Creole | Latn | No | Yes | No | Tesseract tessdata_fast langpack 'hat' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). py3langid label 'ht'. |
| `bo` | Tibetan | Tibt | No | No | No | Tesseract tessdata_fast langpack 'bod' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). Not a label in py3langid's bundled model (language ID unavailable). |
| `dv` | Dhivehi | Thaa | Yes | No | No | Tesseract tessdata_fast langpack 'div' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). Not a label in py3langid's bundled model (language ID unavailable). |
| `ti` | Tigrinya | Ethi | No | No | No | Tesseract tessdata_fast langpack 'tir' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). Not a label in py3langid's bundled model (language ID unavailable). |
| `to` | Tongan | Latn | No | No | No | Tesseract tessdata_fast langpack 'ton' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). Not a label in py3langid's bundled model (language ID unavailable). |
| `chr` | Cherokee | Cher | No | No | No | Tesseract tessdata_fast langpack 'chr' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). Not a label in py3langid's bundled model (language ID unavailable). |
| `iu` | Inuktitut | Cans | No | No | No | Tesseract tessdata_fast langpack 'iku' documented upstream but not installed in this checkout (only 'eng' is present; fetch via `brew install tesseract-lang` or manual tessdata download). Not a label in py3langid's bundled model (language ID unavailable). |
| `ku` | Kurdish | Arab | Yes | No | No | No known Tesseract tessdata_fast langpack for this language. py3langid label 'ku'. |

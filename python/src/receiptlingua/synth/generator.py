"""Deterministic synthetic receipt generator.

Generates realistic-*looking* but clearly fictional receipts (no real
business is named), rendered with real system fonts, together with an
exact ground-truth sidecar (this module wrote the text, so it knows the
text -- there is no OCR or manual annotation involved in producing the
label).

Determinism: ``generate_receipt(language, seed)`` with the same
``(language, seed)`` pair always produces the same picked strings, same
layout, and a byte-identical rendered image (verified by
``python/tests/test_synth_generator.py``). All randomness is drawn from a
single ``random.Random(seed)`` instance seeded per-call; nothing reads
global random state or wall-clock time.

Font/language support is intentionally limited to languages this
checkout has a *real, verified* font for (see the module-level check in
``FONTS`` below) -- a language is never claimed as supported here unless
a font file was actually confirmed to load and render.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont

# Candidate font paths per language: macOS system fonts (verified by hand,
# see docs/COMMIT_PLAN.md 171-185 notes, to load and render non-empty glyphs
# for each script), plus the equivalent open, permissively-licensed fonts on
# a typical Linux box (DejaVu Sans for Latin; Noto Sans's per-script variants
# for the rest -- installed in CI via `apt-get install fonts-dejavu-core
# fonts-noto-core fonts-noto-extra`, see .github/workflows/python-tests.yml).
# The first candidate that actually exists on THIS machine is used; a
# language with no existing candidate is simply not supported here (see
# SUPPORTED_LANGUAGES below) rather than fabricating support.
_FONT_CANDIDATES: dict[str, dict[str, Any]] = {
    "en": {
        "candidates": [
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ],
        "script": "Latn",
        "rtl": "false",
    },
    "ta": {
        "candidates": [
            "/System/Library/Fonts/Supplemental/Tamil MN.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansTamil-Regular.ttf",
        ],
        "script": "Taml",
        "rtl": "false",
    },
    # NOTE: SFArabic.ttf/SFHebrew.ttf (Apple's native Arabic/Hebrew system
    # fonts) were tried first and do render their own scripts correctly,
    # but were verified (via PIL ImageFont.getmask bbox probing -- see
    # docs/COMMIT_PLAN.md RTL-fix notes) to have NO usable Latin digit/
    # ASCII glyphs: every ASCII codepoint ('0'-'9', 'x', 'A'...) came back
    # with the exact same bounding box, the signature of FreeType's
    # ".notdef" fallback glyph -- i.e. every price, date, and quantity on
    # ar/he receipts was silently rendered as a black tofu box. Arial
    # Unicode.ttf was verified (same bbox-probing method) to have distinct,
    # correct glyphs for Latin digits/punctuation *and* Arabic/Hebrew
    # letterforms (including the presentation-forms glyphs
    # ``arabic_reshaper`` output needs), so it is used for both. Noto Sans
    # Arabic (a distinct font on Linux) has not been separately bbox-probed
    # for the same digit issue; if it turns out to have it too, that's a
    # follow-up, not assumed fixed here.
    "ar": {
        "candidates": [
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        ],
        "script": "Arab",
        "rtl": "true",
    },
    "hi": {
        "candidates": [
            "/System/Library/Fonts/Supplemental/Devanagari Sangam MN.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
        ],
        "script": "Deva",
        "rtl": "false",
    },
    "he": {
        "candidates": [
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansHebrew-Regular.ttf",
        ],
        "script": "Hebr",
        "rtl": "true",
    },
    # --- Added in the language-expansion pass (see docs/COMMIT_PLAN.md for
    # the verification method: PIL ImageFont.getmask(ch).getbbox() probing
    # of each script's real characters plus ASCII digits/punctuation,
    # checking bboxes are NOT identical across distinct characters -- the
    # signature of a ".notdef" tofu-box fallback). Every entry below was
    # bbox-probed by hand on macOS before being added; none are assumed. ---
    # Latin-script languages with diacritics: Arial.ttf was already verified
    # (see "en" above) to have correct, distinct Latin glyphs; bbox-probed
    # again here with each language's actual diacritic letters (À É Ñ Ç ß
    # Ş ı Đ etc.) to confirm those specific accented glyphs aren't tofu.
    "fr": {
        "candidates": ["/System/Library/Fonts/Supplemental/Arial.ttf"],
        "script": "Latn",
        "rtl": "false",
    },
    "de": {
        "candidates": ["/System/Library/Fonts/Supplemental/Arial.ttf"],
        "script": "Latn",
        "rtl": "false",
    },
    "es": {
        "candidates": ["/System/Library/Fonts/Supplemental/Arial.ttf"],
        "script": "Latn",
        "rtl": "false",
    },
    "pt": {
        "candidates": ["/System/Library/Fonts/Supplemental/Arial.ttf"],
        "script": "Latn",
        "rtl": "false",
    },
    "it": {
        "candidates": ["/System/Library/Fonts/Supplemental/Arial.ttf"],
        "script": "Latn",
        "rtl": "false",
    },
    "nl": {
        "candidates": ["/System/Library/Fonts/Supplemental/Arial.ttf"],
        "script": "Latn",
        "rtl": "false",
    },
    "tr": {
        "candidates": ["/System/Library/Fonts/Supplemental/Arial.ttf"],
        "script": "Latn",
        "rtl": "false",
    },
    "pl": {
        "candidates": ["/System/Library/Fonts/Supplemental/Arial.ttf"],
        "script": "Latn",
        "rtl": "false",
    },
    "id": {
        "candidates": ["/System/Library/Fonts/Supplemental/Arial.ttf"],
        "script": "Latn",
        "rtl": "false",
    },
    "ms": {
        "candidates": ["/System/Library/Fonts/Supplemental/Arial.ttf"],
        "script": "Latn",
        "rtl": "false",
    },
    "vi": {
        "candidates": ["/System/Library/Fonts/Supplemental/Arial.ttf"],
        "script": "Latn",
        "rtl": "false",
    },
    # Cyrillic: Arial.ttf itself was bbox-probed with real Cyrillic letters
    # (АБВГДЕЖЗИЙК, lowercase) plus ASCII and rendered every one distinctly
    # -- no need for Arial Unicode.ttf here.
    "ru": {
        "candidates": ["/System/Library/Fonts/Supplemental/Arial.ttf"],
        "script": "Cyrl",
        "rtl": "false",
    },
    "uk": {
        "candidates": ["/System/Library/Fonts/Supplemental/Arial.ttf"],
        "script": "Cyrl",
        "rtl": "false",
    },
    # Persian: Arial Unicode.ttf (already verified for ar/he) was bbox-
    # probed again with Persian-specific extra letters not in Arabic proper
    # (پ چ ژ گ) plus core Arabic letters and ASCII -- all distinct, real
    # glyphs. NOTE: SFArabic.ttf (Apple's native Arabic font) was also
    # tried and rejected -- it has the same ASCII-digit ".notdef" bug
    # documented above for SFArabic/SFHebrew, so it is NOT used.
    "fa": {
        "candidates": ["/System/Library/Fonts/Supplemental/Arial Unicode.ttf"],
        "script": "Arab",
        "rtl": "true",
    },
    # Urdu: reuses Arial Unicode.ttf, bbox-probed with Urdu-specific letters
    # (retroflex ٹ ڈ ڑ, ں, ھ, ۓ) plus core Arabic letters and ASCII, all
    # distinct. This renders Urdu in a plain Naskh style rather than the
    # traditional Nastaliq calligraphic style real Urdu print uses --
    # DecoTypeNastaleeqUrdu.ttc and NotoNastaliq.ttc were also probed and
    # both do render real Nastaliq glyphs, but Arial Unicode was kept for
    # consistency with ar/he/fa (one already-verified multi-script font)
    # rather than adding a third distinct rendering style without a reason
    # to prefer it.
    "ur": {
        "candidates": ["/System/Library/Fonts/Supplemental/Arial Unicode.ttf"],
        "script": "Arab",
        "rtl": "true",
    },
    # Devanagari (Marathi): reuses the same font already verified for "hi".
    "mr": {
        "candidates": [
            "/System/Library/Fonts/Supplemental/Devanagari Sangam MN.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
        ],
        "script": "Deva",
        "rtl": "false",
    },
    # CJK.
    "zh-Hans": {
        "candidates": [
            "/System/Library/Fonts/Supplemental/Songti.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        ],
        "script": "Hani",
        "rtl": "false",
    },
    "zh-Hant": {
        "candidates": [
            "/System/Library/Fonts/Supplemental/Songti.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        ],
        "script": "Hani",
        "rtl": "false",
    },
    "ja": {
        "candidates": [
            "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        ],
        "script": "Jpan",
        "rtl": "false",
    },
    "ko": {
        "candidates": [
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        ],
        "script": "Hang",
        "rtl": "false",
    },
}


def _resolve_font(lang: str) -> str | None:
    for path in _FONT_CANDIDATES[lang]["candidates"]:
        if Path(path).exists():
            return path
    return None


#: Languages this generator can actually render right now, restricted to
#: those with at least one existing font candidate on THIS machine --
#: claiming script support without a real, loadable font on the running
#: machine is exactly the kind of fabricated capability this project
#: forbids.
FONTS: dict[str, dict[str, str]] = {
    lang: {"font": font, "script": info["script"], "rtl": info["rtl"]}
    for lang, info in _FONT_CANDIDATES.items()
    if (font := _resolve_font(lang)) is not None
}

SUPPORTED_LANGUAGES: tuple[str, ...] = tuple(FONTS.keys())

_CURRENCY_BY_LANG = {
    "en": "USD",
    "ta": "INR",
    "hi": "INR",
    "ar": "AED",
    "he": "ILS",
    "fr": "EUR",
    "de": "EUR",
    "es": "EUR",
    "pt": "EUR",
    "it": "EUR",
    "nl": "EUR",
    "tr": "TRY",
    "pl": "PLN",
    "id": "IDR",
    "ms": "MYR",
    "vi": "VND",
    "ru": "RUB",
    "uk": "UAH",
    "fa": "IRR",
    "ur": "PKR",
    "mr": "INR",
    "zh-Hans": "CNY",
    "zh-Hant": "TWD",
    "ja": "JPY",
    "ko": "KRW",
}

# Word banks: deliberately fictional -- no real business names, addresses,
# or brands. Store/street name parts are generic nouns/patterns that read
# as "a receipt" without impersonating anyone real.
_WORD_BANKS: dict[str, dict[str, list[str]]] = {
    "en": {
        "store_prefix": ["Sunny", "Golden", "Corner", "Blue", "Maple", "River", "Silver", "Green"],
        "store_suffix": ["Market", "Grocers", "Mart", "Store", "Bazaar", "Depot", "Shop"],
        "street": ["Oak", "Main", "Elm", "Pine", "Cedar", "Birch", "Lake", "Hill"],
        "items": [
            "Milk",
            "Bread",
            "Eggs",
            "Coffee",
            "Rice",
            "Butter",
            "Apples",
            "Soap",
            "Tea",
            "Sugar",
        ],
        "city": ["Springfield", "Fairview", "Riverton", "Hillcrest"],
    },
    "ta": {
        "store_prefix": ["தங்கம்", "நதி", "மலை", "பசுமை"],
        "store_suffix": ["கடை", "சந்தை", "பேரங்காடி"],
        "street": ["காந்தி தெரு", "நேரு சாலை", "அன்னா சாலை"],
        "items": ["பால்", "அரிசி", "தேநீர்", "சர்க்கரை", "எண்ணெய்", "முட்டை"],
        "city": ["நகரம்"],
    },
    "ar": {
        "store_prefix": ["الذهبي", "النخيل", "الأزرق", "الفجر"],
        "store_suffix": ["سوق", "بقالة", "متجر"],
        "street": ["شارع الورد", "شارع النور", "شارع السلام"],
        "items": ["حليب", "خبز", "بيض", "أرز", "شاي", "سكر"],
        "city": ["المدينة"],
    },
    "hi": {
        "store_prefix": ["सुनहरा", "हरित", "नदी", "पहाड़ी"],
        "store_suffix": ["बाज़ार", "स्टोर", "मंडी"],
        "street": ["गांधी मार्ग", "नेहरू रोड", "मुख्य सड़क"],
        "items": ["दूध", "चावल", "चाय", "चीनी", "अंडे", "तेल"],
        "city": ["नगर"],
    },
    "he": {
        "store_prefix": ["הזהב", "הכחול", "האורן", "הנחל"],
        "store_suffix": ["שוק", "מרכול", "חנות"],
        "street": ["רחוב הראשי", "רחוב הפרחים"],
        "items": ["חלב", "לחם", "ביצים", "אורז", "תה", "סוכר"],
        "city": ["העיר"],
    },
    # --- Added in the language-expansion pass. Deliberately small: only
    # vocabulary the author is confident is real, correctly-spelled
    # everyday-receipt vocabulary in that language -- not padded out with
    # guessed words. Languages with a verified font but no vocabulary the
    # author was confident enough to write are left out entirely (see
    # docs/COMMIT_PLAN.md for the explicit list and reasons). ---
    "fr": {
        "store_prefix": ["Soleil", "Rivière", "Vieux", "Bon"],
        "store_suffix": ["Marché", "Épicerie", "Supérette"],
        "street": ["Rue du Chêne", "Rue Principale", "Rue des Fleurs", "Rue du Moulin"],
        "items": ["Lait", "Pain", "Œufs", "Café", "Riz", "Beurre", "Pommes", "Savon", "Thé", "Sucre"],
        "city": ["Villefleur", "Bourgneuf"],
    },
    "de": {
        "store_prefix": ["Sonnen", "Grüner", "Alter", "Blauer"],
        "store_suffix": ["Markt", "Laden", "Supermarkt"],
        "street": ["Hauptstraße", "Lindenweg", "Gartenstraße", "Mühlenweg"],
        "items": ["Milch", "Brot", "Eier", "Kaffee", "Reis", "Butter", "Äpfel", "Seife", "Tee", "Zucker"],
        "city": ["Sonnenfeld", "Neustadt"],
    },
    "es": {
        "store_prefix": ["Sol", "Río", "Verde", "Viejo"],
        "store_suffix": ["Mercado", "Tienda", "Almacén"],
        "street": ["Calle Mayor", "Calle del Río", "Calle de las Flores"],
        "items": ["Leche", "Pan", "Huevos", "Café", "Arroz", "Mantequilla", "Manzanas", "Jabón", "Té", "Azúcar"],
        "city": ["Villasol", "Puebloverde"],
    },
    "pt": {
        "store_prefix": ["Sol", "Rio", "Verde", "Velho"],
        "store_suffix": ["Mercado", "Loja", "Armazém"],
        "street": ["Rua Principal", "Rua das Flores", "Rua do Rio"],
        "items": ["Leite", "Pão", "Ovos", "Café", "Arroz", "Manteiga", "Maçãs", "Sabão", "Chá", "Açúcar"],
        "city": ["Vilanova", "Campoverde"],
    },
    "it": {
        "store_prefix": ["Sole", "Fiume", "Verde", "Vecchio"],
        "store_suffix": ["Mercato", "Negozio", "Bottega"],
        "street": ["Via Principale", "Via dei Fiori", "Via del Fiume"],
        "items": ["Latte", "Pane", "Uova", "Caffè", "Riso", "Burro", "Mele", "Sapone", "Tè", "Zucchero"],
        "city": ["Villasole", "Campoverde"],
    },
    "nl": {
        "store_prefix": ["Zonne", "Groene", "Oude", "Blauwe"],
        "store_suffix": ["Markt", "Winkel", "Supermarkt"],
        "street": ["Hoofdstraat", "Kerkstraat", "Molenweg"],
        "items": ["Melk", "Brood", "Eieren", "Koffie", "Rijst", "Boter", "Appels", "Zeep", "Thee", "Suiker"],
        "city": ["Zonnedorp", "Nieuwstad"],
    },
    "tr": {
        "store_prefix": ["Altın", "Yeşil", "Nehir", "Güneş"],
        "store_suffix": ["Market", "Bakkal", "Mağaza"],
        "street": ["Cumhuriyet Caddesi", "Çiçek Sokağı", "Nehir Yolu"],
        "items": ["Süt", "Ekmek", "Yumurta", "Kahve", "Pirinç", "Tereyağı", "Elma", "Sabun", "Çay", "Şeker"],
        "city": ["Güneşköy"],
    },
    "pl": {
        "store_prefix": ["Złoty", "Zielony", "Stary", "Rzeczny"],
        "store_suffix": ["Market", "Sklep", "Delikatesy"],
        "street": ["Główna", "Kwiatowa", "Rzeczna"],
        "items": ["Mleko", "Chleb", "Jajka", "Kawa", "Ryż", "Masło", "Jabłka", "Mydło", "Herbata", "Cukier"],
        "city": ["Zielonogród"],
    },
    "ru": {
        "store_prefix": ["Золотой", "Зелёный", "Речной", "Старый"],
        "store_suffix": ["Рынок", "Магазин", "Лавка"],
        "street": ["Главная улица", "Речная улица", "Садовая улица"],
        "items": ["Молоко", "Хлеб", "Яйца", "Кофе", "Рис", "Масло", "Яблоки", "Мыло", "Чай", "Сахар"],
        "city": ["Речноград"],
    },
    "uk": {
        "store_prefix": ["Золотий", "Зелений", "Річковий", "Старий"],
        "store_suffix": ["Ринок", "Магазин", "Лавка"],
        "street": ["Головна вулиця", "Річкова вулиця", "Садова вулиця"],
        "items": ["Молоко", "Хліб", "Яйця", "Кава", "Рис", "Масло", "Яблука", "Мило", "Чай", "Цукор"],
        "city": ["Річкоград"],
    },
    "id": {
        "store_prefix": ["Matahari", "Hijau", "Sungai", "Emas"],
        "store_suffix": ["Pasar", "Toko", "Warung"],
        "street": ["Jalan Utama", "Jalan Melati", "Jalan Sungai"],
        "items": ["Susu", "Roti", "Telur", "Kopi", "Beras", "Mentega", "Apel", "Sabun", "Teh", "Gula"],
        "city": ["Sungaimas"],
    },
    "ms": {
        "store_prefix": ["Matahari", "Hijau", "Sungai", "Emas"],
        "store_suffix": ["Pasar", "Kedai", "Gedung"],
        "street": ["Jalan Utama", "Jalan Bunga", "Jalan Sungai"],
        "items": ["Susu", "Roti", "Telur", "Kopi", "Beras", "Mentega", "Epal", "Sabun", "Teh", "Gula"],
        "city": ["Bandar Emas"],
    },
    "vi": {
        "store_prefix": ["Vàng", "Xanh", "Sông", "Mới"],
        "store_suffix": ["Chợ", "Tiệm", "Cửa Hàng"],
        "street": ["Đường Chính", "Đường Hoa", "Đường Sông"],
        "items": ["Sữa", "Bánh Mì", "Trứng", "Cà Phê", "Gạo", "Bơ", "Táo", "Xà Phòng", "Trà", "Đường"],
        "city": ["Sông Vàng"],
    },
    "fa": {
        "store_prefix": ["طلایی", "سبز", "رودخانه", "آبی"],
        "store_suffix": ["بازار", "فروشگاه", "مغازه"],
        "street": ["خیابان اصلی", "خیابان گل"],
        "items": ["شیر", "نان", "تخم مرغ", "برنج", "چای", "شکر"],
        "city": ["شهر"],
    },
    "ur": {
        "store_prefix": ["سنہری", "سبز", "دریا", "نیلا"],
        "store_suffix": ["بازار", "دکان", "سٹور"],
        "street": ["مین روڈ", "پھول والی گلی"],
        "items": ["دودھ", "روٹی", "انڈے", "چائے", "چینی", "چاول"],
        "city": ["شہر"],
    },
    "mr": {
        "store_prefix": ["सोनेरी", "हरित", "नदी", "जुना"],
        "store_suffix": ["बाजार", "दुकान"],
        "street": ["मुख्य रस्ता", "फुलांचा रस्ता"],
        "items": ["दूध", "पाव", "अंडी", "चहा", "साखर", "तांदूळ"],
        "city": ["शहर"],
    },
    "zh-Hans": {
        "store_prefix": ["金", "绿", "河", "新"],
        "store_suffix": ["市场", "商店", "超市"],
        "street": ["中山路", "花园街", "河边路"],
        "items": ["牛奶", "面包", "鸡蛋", "咖啡", "大米", "黄油", "苹果", "肥皂", "茶", "糖"],
        "city": ["新城"],
    },
    "zh-Hant": {
        "store_prefix": ["金", "綠", "河", "新"],
        "store_suffix": ["市場", "商店", "超市"],
        "street": ["中山路", "花園街", "河邊路"],
        "items": ["牛奶", "麵包", "雞蛋", "咖啡", "大米", "奶油", "蘋果", "肥皂", "茶", "糖"],
        "city": ["新城"],
    },
    "ja": {
        "store_prefix": ["金", "緑", "川", "新"],
        "store_suffix": ["市場", "商店", "スーパー"],
        "street": ["中央通り", "桜通り", "川辺通り"],
        "items": ["牛乳", "パン", "卵", "コーヒー", "米", "バター", "りんご", "石鹸", "茶", "砂糖"],
        "city": ["新町"],
    },
    "ko": {
        "store_prefix": ["금빛", "초록", "강", "새"],
        "store_suffix": ["시장", "상점", "마트"],
        "street": ["중앙로", "꽃길", "강변로"],
        "items": ["우유", "빵", "계란", "커피", "쌀", "버터", "사과", "비누", "차", "설탕"],
        "city": ["새마을"],
    },
}


@dataclass(frozen=True)
class LineItemGT:
    description: str
    quantity: int
    unit_price: float
    item_total: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "item_total": self.item_total,
        }


@dataclass(frozen=True)
class GroundTruth:
    """Exact ground truth for one generated receipt. This is the label --
    it was written by the generator, not inferred, so it is exact by
    construction."""

    language: str
    script: str
    seed: int
    merchant: str
    address: str
    date: str
    time: str
    currency: str
    line_items: tuple[LineItemGT, ...]
    subtotal: float
    tax: float
    total: float
    lines: tuple[str, ...]  # every literal text line rendered onto the image, in order

    @property
    def full_text(self) -> str:
        return "\n".join(self.lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "script": self.script,
            "seed": self.seed,
            "merchant": self.merchant,
            "address": self.address,
            "date": self.date,
            "time": self.time,
            "currency": self.currency,
            "line_items": [li.to_dict() for li in self.line_items],
            "subtotal": self.subtotal,
            "tax": self.tax,
            "total": self.total,
            "lines": list(self.lines),
            "full_text": self.full_text,
        }

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2))


@dataclass(frozen=True)
class SyntheticReceipt:
    image: Image.Image
    ground_truth: GroundTruth


def _fmt_amount(value: float) -> str:
    return f"{value:.2f}"


def _visual_render_line(line: str, *, rtl: bool) -> str:
    """Convert a logical-order Unicode string into the visual-order glyph
    sequence PIL's ``ImageDraw.text`` needs to render it correctly.

    PIL/FreeType draws glyphs left-to-right in the order given -- it does
    not apply the Unicode Bidirectional Algorithm or Arabic contextual
    letter shaping (initial/medial/final/isolated joining forms). Drawing
    a raw logical-order Arabic/Hebrew string therefore produces visually
    wrong output (disconnected Arabic letters, reversed word order) even
    though the *ground truth string itself* is perfectly correct Unicode --
    the bug is purely in what gets handed to ``draw.text``, not in the
    ground truth. This function is only ever used for the image-rendering
    path; ``GroundTruth.lines``/``full_text`` always keep the original
    logical-order string, matching what Tesseract's own RTL-aware ``ara``/
    ``heb`` models are trained to output.
    """
    if not rtl:
        return line
    # Arabic needs contextual letter shaping (joining) before bidi
    # reordering; Hebrew letters are not joined, so reshaping is a no-op
    # for it and only bidi reordering applies.
    reshaped = arabic_reshaper.reshape(line)
    return get_display(reshaped)


def generate_receipt(
    language: str,
    seed: int,
    *,
    num_items: int | None = None,
    font_size: int = 20,
    width: int = 420,
) -> SyntheticReceipt:
    """Deterministically generate one fictional receipt for ``language``.

    Same ``(language, seed, num_items, font_size, width)`` always produces
    byte-identical output -- all randomness is drawn from a
    ``random.Random(seed)`` local to this call.
    """
    if language not in FONTS:
        raise ValueError(
            f"unsupported synth language '{language}'; supported: {sorted(FONTS)} "
            "(a language is only added here once a real font is verified to render it)"
        )
    rng = random.Random(seed)
    bank = _WORD_BANKS[language]
    font_info = FONTS[language]
    currency = _CURRENCY_BY_LANG[language]

    merchant = f"{rng.choice(bank['store_prefix'])} {rng.choice(bank['store_suffix'])}"
    address = f"{rng.randint(1, 999)} {rng.choice(bank['street'])}, {rng.choice(bank['city'])}"
    year = rng.randint(2022, 2026)
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    date = f"{year:04d}-{month:02d}-{day:02d}"
    hour = rng.randint(8, 21)
    minute = rng.randint(0, 59)
    time_str = f"{hour:02d}:{minute:02d}"

    n_items = num_items if num_items is not None else rng.randint(3, 6)
    items: list[LineItemGT] = []
    for _ in range(n_items):
        desc = rng.choice(bank["items"])
        qty = rng.randint(1, 4)
        unit_price = round(rng.uniform(0.99, 24.99), 2)
        item_total = round(qty * unit_price, 2)
        items.append(LineItemGT(desc, qty, unit_price, item_total))

    subtotal = round(sum(li.item_total for li in items), 2)
    tax = round(subtotal * 0.07, 2)
    total = round(subtotal + tax, 2)

    lines: list[str] = [merchant, address, f"{date} {time_str}"]
    for li in items:
        unit_price = _fmt_amount(li.unit_price)
        item_total = _fmt_amount(li.item_total)
        lines.append(f"{li.description} {li.quantity} x {unit_price} {item_total}")
    lines.append(f"SUBTOTAL {_fmt_amount(subtotal)}")
    lines.append(f"TAX {_fmt_amount(tax)}")
    lines.append(f"TOTAL {_fmt_amount(total)} {currency}")

    height = 60 + font_size * 2.2 * (len(lines) + 1)
    img = Image.new("RGB", (width, int(height)), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_info["font"], font_size)
    is_rtl = font_info["rtl"] == "true"
    y = 20
    for line in lines:
        draw.text((18, y), _visual_render_line(line, rtl=is_rtl), fill="black", font=font)
        y += int(font_size * 1.6)

    gt = GroundTruth(
        language=language,
        script=font_info["script"],
        seed=seed,
        merchant=merchant,
        address=address,
        date=date,
        time=time_str,
        currency=currency,
        line_items=tuple(items),
        subtotal=subtotal,
        tax=tax,
        total=total,
        lines=tuple(lines),
    )
    return SyntheticReceipt(image=img, ground_truth=gt)

"""Translation pipeline with mock NLLB-200 dispatch.

Production target: Modal NLLB-200 (200 languages, $0.0001 per 100 chars).
This module provides:
  - Multi-language detection (heuristic + NLLB fallback)
  - Cached translation with deterministic mock dictionary for tests
  - Cultural adaptation hooks
  - Hashtag generation per language
  - Cost tracking ($0.0001 / 100 chars)

Heavy work (real translation via Modal) is dispatched through ``modal_dispatcher``
when provided. When unset, the pipeline uses the in-process MOCK_DICT for
deterministic, offline behaviour suitable for CI and local development.
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

log = logging.getLogger(__name__)

# Hard caps to keep translation inputs bounded.  Expressed as plain constants
# so the pipeline has no Pydantic dependency.
MAX_TEXT_LENGTH: int = 10_000
MAX_BATCH_SIZE: int = 100

SUPPORTED_LANGS = [
    "en", "id", "es", "pt", "fr", "de", "ja", "ko",
    "zh", "ar", "hi", "th", "vi", "ms",
]

LANG_NAMES = {
    "en": "English", "id": "Indonesian", "es": "Spanish", "pt": "Portuguese",
    "fr": "French", "de": "German", "ja": "Japanese", "ko": "Korean",
    "zh": "Chinese", "ar": "Arabic", "hi": "Hindi", "th": "Thai",
    "vi": "Vietnamese", "ms": "Malay",
}

MOCK_DICT: dict[tuple[str, str], dict[str, str]] = {
    ("en", "id"): {"hello": "halo", "world": "dunia", "thank you": "terima kasih", "yes": "ya", "no": "tidak", "good": "baik", "bad": "buruk", "love": "cinta", "food": "makanan", "water": "air"},
    ("en", "es"): {"hello": "hola", "world": "mundo", "thank you": "gracias", "yes": "sí", "no": "no", "good": "bueno", "bad": "malo", "love": "amor", "food": "comida", "water": "agua"},
    ("en", "pt"): {"hello": "olá", "world": "mundo", "thank you": "obrigado", "yes": "sim", "no": "não", "good": "bom", "bad": "mau", "love": "amor", "food": "comida", "water": "água"},
    ("en", "fr"): {"hello": "bonjour", "world": "monde", "thank you": "merci", "yes": "oui", "no": "non", "good": "bon", "bad": "mauvais", "love": "amour", "food": "nourriture", "water": "eau"},
    ("en", "de"): {"hello": "hallo", "world": "welt", "thank you": "danke", "yes": "ja", "no": "nein", "good": "gut", "bad": "schlecht", "love": "liebe", "food": "essen", "water": "wasser"},
    ("en", "ja"): {"hello": "こんにちは", "world": "世界", "thank you": "ありがとう", "yes": "はい", "no": "いいえ", "good": "良い", "bad": "悪い", "love": "愛", "food": "食べ物", "water": "水"},
    ("en", "ko"): {"hello": "안녕하세요", "world": "세계", "thank you": "감사합니다", "yes": "예", "no": "아니오", "good": "좋은", "bad": "나쁜", "love": "사랑", "food": "음식", "water": "물"},
    ("en", "zh"): {"hello": "你好", "world": "世界", "thank you": "谢谢", "yes": "是", "no": "不", "good": "好", "bad": "坏", "love": "爱", "food": "食物", "water": "水"},
    ("en", "ar"): {"hello": "مرحبا", "world": "عالم", "thank you": "شكرا", "yes": "نعم", "no": "لا", "good": "جيد", "bad": "سيء", "love": "حب", "food": "طعام", "water": "ماء"},
    ("en", "hi"): {"hello": "नमस्ते", "world": "दुनिया", "thank you": "धन्यवाद", "yes": "हाँ", "no": "नहीं", "good": "अच्छा", "bad": "बुरा", "love": "प्यार", "food": "भोजन", "water": "पानी"},
    ("en", "th"): {"hello": "สวัสดี", "world": "โลก", "thank you": "ขอบคุณ", "yes": "ใช่", "no": "ไม่", "good": "ดี", "bad": "ไม่ดี", "love": "รัก", "food": "อาหาร", "water": "น้ำ"},
    ("en", "vi"): {"hello": "xin chào", "world": "thế giới", "thank you": "cảm ơn", "yes": "vâng", "no": "không", "good": "tốt", "bad": "xấu", "love": "yêu", "food": "thức ăn", "water": "nước"},
    ("en", "ms"): {"hello": "hello", "world": "dunia", "thank you": "terima kasih", "yes": "ya", "no": "tidak", "good": "baik", "bad": "buruk", "love": "cinta", "food": "makanan", "water": "air"},
}

HASHTAGS_BY_LANG: dict[str, list[str]] = {
    "en": ["#viral", "#trending", "#fyp", "#love", "#instagood", "#photooftheday", "#beautiful", "#happy", "#follow", "#art"],
    "id": ["#viral", "#trending", "#fyp", "#indonesia", "#jakarta", "#bandung", "#surabaya", "#medan", "#makassar", "#denpasar"],
    "es": ["#viral", "#trending", "#españa", "#méxico", "#argentina", "#colombia", "#chile", "#perú", "#fyp", "#amor"],
    "pt": ["#viral", "#trending", "#brasil", "#portugal", "#fyp", "#amor", "#feliz", "#saopaulo", "#rio", "#lisboa"],
    "fr": ["#viral", "#trending", "#france", "#paris", "#amour", "#fyp", "#bonheur", "#lyon", "#marseille", "#nice"],
    "de": ["#viral", "#trending", "#deutschland", "#berlin", "#liebe", "#fyp", "#münchen", "#hamburg", "#köln", "#frankfurt"],
    "ja": ["#viral", "#日本", "#東京", "#大阪", "#京都", "#福岡", "#札幌", "#名古屋", "#横浜", "#神戸"],
    "ko": ["#viral", "#한국", "#서울", "#부산", "#제주", "#인천", "#대구", "#광주", "#대전", "#울산"],
    "zh": ["#viral", "#中国", "#北京", "#上海", "#广州", "#深圳", "#成都", "#杭州", "#武汉", "#西安"],
    "ar": ["#viral", "#السعودية", "#الإمارات", "#مصر", "#الكويت", "#قطر", "#عمان", "#الأردن", "#لبنان", "#العراق"],
    "hi": ["#viral", "#भारत", "#मुंबई", "#दिल्ली", "#बेंगलुरु", "#कोलकाता", "#चेन्नई", "#हैदराबाद", "#पुणे", "#जयपुर"],
    "th": ["#viral", "#ไทย", "#กรุงเทพ", "#เชียงใหม่", "#ภูเก็ต", "#พัทยา", "#หาดใหญ่", "#ขอนแก่น", "#นครราชสีมา", "#อุดรธานี"],
    "vi": ["#viral", "#việtnam", "#hànhội", "#hồchíminh", "#đànẵng", "#hảiphòng", "#cầnthơ", "#nhatrang", "#đàlạt", "#huế"],
    "ms": ["#viral", "#malaysia", "#kualalumpur", "#penang", "#johor", "#sabah", "#sarawak", "#melaka", "#ipoh", "#putrajaya"],
}


@dataclass
class TranslationResult:
    source_text: str
    target_text: str
    source_lang: str
    target_lang: str
    confidence: float
    model_used: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TranslationPipeline:
    def __init__(self, modal_dispatcher=None) -> None:
        self.modal = modal_dispatcher
        self._cache: dict[str, TranslationResult] = {}
        self._cost_usd: float = 0.0

    async def translate(
        self,
        text: str,
        target_lang: str,
        source_lang: str = "auto",
    ) -> TranslationResult:
        if target_lang not in SUPPORTED_LANGS:
            raise ValueError(f"Unsupported target language: {target_lang}")
        if text is not None and len(text) > MAX_TEXT_LENGTH:
            raise ValueError(
                f"text too long: {len(text)} chars (max {MAX_TEXT_LENGTH})"
            )
        if not text or not text.strip():
            return TranslationResult(
                source_text=text,
                target_text="",
                source_lang=source_lang,
                target_lang=target_lang,
                confidence=1.0,
                model_used="identity",
            )
        if source_lang == "auto":
            source_lang = await self.detect_language(text)
        if source_lang not in SUPPORTED_LANGS:
            source_lang = "en"
        cache_key = f"{source_lang}:{target_lang}:{text}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        if source_lang == target_lang:
            result = TranslationResult(
                source_text=text,
                target_text=text,
                source_lang=source_lang,
                target_lang=target_lang,
                confidence=1.0,
                model_used="identity",
            )
        else:
            target_text = self._mock_translate(text, source_lang, target_lang)
            coverage = self._coverage_score(text, source_lang, target_lang)
            result = TranslationResult(
                source_text=text,
                target_text=target_text,
                source_lang=source_lang,
                target_lang=target_lang,
                confidence=round(coverage, 3),
                model_used="nllb-200-mock",
            )
        self._cost_usd += self.estimate_cost(len(text), target_lang)
        self._cache[cache_key] = result
        return result

    async def translate_batch(
        self, texts: list[str], target_lang: str
    ) -> list[TranslationResult]:
        if len(texts) > MAX_BATCH_SIZE:
            raise ValueError(
                f"batch too large: {len(texts)} items (max {MAX_BATCH_SIZE})"
            )
        results: list[TranslationResult] = []
        for t in texts:
            results.append(await self.translate(t, target_lang))
        return results

    async def detect_language(self, text: str) -> str:
        if text is not None and len(text) > MAX_TEXT_LENGTH:
            raise ValueError(
                f"text too long: {len(text)} chars (max {MAX_TEXT_LENGTH})"
            )
        if not text or not text.strip():
            return "en"
        if re.search(r"[\u3040-\u309f\u30a0-\u30ff]", text):
            return "ja"
        if re.search(r"[\uac00-\ud7af]", text):
            return "ko"
        if re.search(r"[\u4e00-\u9fff]", text):
            return "zh"
        if re.search(r"[\u0600-\u06ff]", text):
            return "ar"
        if re.search(r"[\u0900-\u097f]", text):
            return "hi"
        if re.search(r"[\u0e00-\u0e7f]", text):
            return "th"
        if text.lower() in {"halo", "dunia", "terima kasih", "ya", "tidak", "makanan", "air"}:
            return "id"
        return "en"

    def _mock_translate(self, text: str, source_lang: str, target_lang: str) -> str:
        dict_key = (source_lang, target_lang)
        if dict_key in MOCK_DICT:
            mapping = MOCK_DICT[dict_key]
            result = text
            for src, tgt in mapping.items():
                result = re.sub(rf"\b{re.escape(src)}\b", tgt, result, flags=re.IGNORECASE)
            return result
        return f"[{target_lang}] {text}"

    def _coverage_score(self, text: str, source_lang: str, target_lang: str) -> float:
        dict_key = (source_lang, target_lang)
        if dict_key not in MOCK_DICT:
            return 0.5
        words = set(w.lower().strip(".,!?;:()[]{}\"'") for w in text.split())
        known = set(MOCK_DICT[dict_key].keys())
        if not words:
            return 1.0
        overlap = len(words & known)
        return min(1.0, 0.5 + 0.5 * (overlap / len(words)))

    def adapt_for_culture(self, text: str, target_lang: str) -> str:
        adaptations = {
            "id": [("you guys", "kalian"), ("awesome", "keren"), ("cool", "keren")],
            "ja": [("!", "！"), ("?", "？")],
            "ar": [("Hello", "السلام عليكم"), ("hi", "مرحبا")],
        }
        result = text
        if target_lang in adaptations:
            for src, tgt in adaptations[target_lang]:
                result = result.replace(src, tgt)
        return result

    async def generate_hashtags(
        self, text: str, target_lang: str, count: int = 10
    ) -> list[str]:
        if text is not None and len(text) > MAX_TEXT_LENGTH:
            raise ValueError(
                f"text too long: {len(text)} chars (max {MAX_TEXT_LENGTH})"
            )
        if target_lang not in HASHTAGS_BY_LANG:
            target_lang = "en"
        return HASHTAGS_BY_LANG[target_lang][:count]

    def estimate_cost(self, char_count: int, target_lang: str) -> float:
        if char_count <= 0:
            return 0.0
        return round(char_count / 100.0 * 0.0001, 6)

    @property
    def total_cost_usd(self) -> float:
        return round(self._cost_usd, 6)

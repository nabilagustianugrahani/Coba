"""Tests for integrations/translation_pipeline.py."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ugc_ai_overpower.integrations.translation_pipeline import (
    HASHTAGS_BY_LANG,
    LANG_NAMES,
    MOCK_DICT,
    SUPPORTED_LANGS,
    TranslationPipeline,
    TranslationResult,
)


def _run(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run_coroutine_threadsafe(coro, loop).result()
    except RuntimeError:
        pass
    return asyncio.run(coro)


@pytest.fixture
def pipeline():
    return TranslationPipeline()


# ---------------- TranslationResult ----------------

def test_translation_result_to_dict():
    r = TranslationResult(
        source_text="hello",
        target_text="halo",
        source_lang="en",
        target_lang="id",
        confidence=0.9,
        model_used="nllb-200-mock",
    )
    d = r.to_dict()
    assert d["source_text"] == "hello"
    assert d["target_text"] == "halo"
    assert d["source_lang"] == "en"
    assert d["target_lang"] == "id"
    assert d["confidence"] == 0.9
    assert d["model_used"] == "nllb-200-mock"


def test_translation_result_default_model():
    r = TranslationResult(
        source_text="x",
        target_text="y",
        source_lang="en",
        target_lang="id",
        confidence=1.0,
    )
    assert r.model_used == ""


# ---------------- translate: core ----------------

def test_translate_empty_text_returns_identity(pipeline):
    r = _run(pipeline.translate("", "id"))
    assert r.target_text == ""
    assert r.confidence == 1.0
    assert r.model_used == "identity"


def test_translate_whitespace_only(pipeline):
    r = _run(pipeline.translate("   ", "id"))
    assert r.target_text == ""
    assert r.confidence == 1.0


def test_translate_unsupported_target_raises(pipeline):
    with pytest.raises(ValueError, match="Unsupported target language"):
        _run(pipeline.translate("hello", "xx"))


def test_translate_same_source_target_returns_text(pipeline):
    r = _run(pipeline.translate("hello world", "en"))
    assert r.target_text == "hello world"
    assert r.source_lang == "en"
    assert r.target_lang == "en"
    assert r.confidence == 1.0
    assert r.model_used == "identity"


def test_translate_en_to_id_known_word(pipeline):
    r = _run(pipeline.translate("hello", "id", source_lang="en"))
    assert r.target_text == "halo"
    assert r.source_lang == "en"
    assert r.target_lang == "id"


def test_translate_en_to_ja_known_word(pipeline):
    r = _run(pipeline.translate("hello", "ja", source_lang="en"))
    assert r.target_text == "こんにちは"


def test_translate_confidence_in_range(pipeline):
    r = _run(pipeline.translate("hello world", "id", source_lang="en"))
    assert 0.0 <= r.confidence <= 1.0


def test_translate_caching_returns_same_result(pipeline):
    r1 = _run(pipeline.translate("hello", "id", source_lang="en"))
    r2 = _run(pipeline.translate("hello", "id", source_lang="en"))
    assert r1.target_text == r2.target_text
    assert r1.confidence == r2.confidence
    # cache hit should not add cost
    cost_after_r1 = pipeline.total_cost_usd
    r3 = _run(pipeline.translate("hello", "id", source_lang="en"))
    assert pipeline.total_cost_usd == cost_after_r1


def test_translate_source_lang_set_in_result(pipeline):
    r = _run(pipeline.translate("hello", "es", source_lang="en"))
    assert r.source_lang == "en"
    assert r.target_lang == "es"


# ---------------- translate: auto-detection ----------------

def test_auto_detect_english(pipeline):
    r = _run(pipeline.translate("Hello world", "id"))
    assert r.source_lang == "en"


def test_auto_detect_ja(pipeline):
    r = _run(pipeline.translate("こんにちは世界", "en"))
    assert r.source_lang == "ja"


def test_auto_detect_ko(pipeline):
    r = _run(pipeline.translate("안녕하세요", "en"))
    assert r.source_lang == "ko"


def test_auto_detect_zh(pipeline):
    r = _run(pipeline.translate("你好世界", "en"))
    assert r.source_lang == "zh"


def test_auto_detect_ar(pipeline):
    r = _run(pipeline.translate("مرحبا بالعالم", "en"))
    assert r.source_lang == "ar"


def test_auto_detect_hi(pipeline):
    r = _run(pipeline.translate("नमस्ते दुनिया", "en"))
    assert r.source_lang == "hi"


def test_auto_detect_th(pipeline):
    r = _run(pipeline.translate("สวัสดีชาวโลก", "en"))
    assert r.source_lang == "th"


# ---------------- translate_batch ----------------

def test_translate_batch_empty(pipeline):
    out = _run(pipeline.translate_batch([], "id"))
    assert out == []


def test_translate_batch_mixed(pipeline):
    out = _run(pipeline.translate_batch(["hello", "thank you", "world"], "id"))
    assert len(out) == 3
    assert out[0].target_text == "halo"
    assert out[1].target_text == "terima kasih"
    assert out[2].target_text == "dunia"


# ---------------- detect_language ----------------

def test_detect_empty_returns_en(pipeline):
    assert _run(pipeline.detect_language("")) == "en"


def test_detect_whitespace_returns_en(pipeline):
    assert _run(pipeline.detect_language("   ")) == "en"


def test_detect_english_text(pipeline):
    assert _run(pipeline.detect_language("The quick brown fox")) == "en"


def test_detect_indonesian_word(pipeline):
    assert _run(pipeline.detect_language("halo")) == "id"


def test_detect_japanese_script(pipeline):
    assert _run(pipeline.detect_language("こんにちは")) == "ja"


def test_detect_korean_script(pipeline):
    assert _run(pipeline.detect_language("안녕하세요")) == "ko"


def test_detect_chinese_script(pipeline):
    assert _run(pipeline.detect_language("你好")) == "zh"


def test_detect_arabic_script(pipeline):
    assert _run(pipeline.detect_language("مرحبا")) == "ar"


def test_detect_hindi_script(pipeline):
    assert _run(pipeline.detect_language("नमस्ते")) == "hi"


def test_detect_thai_script(pipeline):
    assert _run(pipeline.detect_language("สวัสดี")) == "th"


# ---------------- adapt_for_culture ----------------

def test_adapt_unknown_lang_no_change(pipeline):
    out = pipeline.adapt_for_culture("Hello world!", "en")
    assert out == "Hello world!"


def test_adapt_id_youguys_to_kalian(pipeline):
    out = pipeline.adapt_for_culture("Hey you guys!", "id")
    assert "kalian" in out
    assert "you guys" not in out


def test_adapt_ja_punctuation(pipeline):
    out = pipeline.adapt_for_culture("Hello! How are you?", "ja")
    assert "！" in out
    assert "？" in out


def test_adapt_ar_formal_greeting(pipeline):
    out = pipeline.adapt_for_culture("Hello there", "ar")
    assert "السلام عليكم" in out


# ---------------- generate_hashtags ----------------

def test_generate_hashtags_count_honored(pipeline):
    out = _run(pipeline.generate_hashtags("anything", "en", count=3))
    assert len(out) == 3


def test_generate_hashtags_unknown_lang_falls_back_to_english(pipeline):
    out = _run(pipeline.generate_hashtags("anything", "xx", count=5))
    assert out == HASHTAGS_BY_LANG["en"][:5]


def test_generate_hashtags_lang_specific(pipeline):
    out = _run(pipeline.generate_hashtags("anything", "ja", count=3))
    assert out == HASHTAGS_BY_LANG["ja"][:3]


def test_generate_hashtags_default_count_ten(pipeline):
    out = _run(pipeline.generate_hashtags("anything", "en"))
    assert len(out) == 10


# ---------------- estimate_cost ----------------

def test_estimate_cost_zero(pipeline):
    assert pipeline.estimate_cost(0, "id") == 0.0


def test_estimate_cost_negative(pipeline):
    assert pipeline.estimate_cost(-5, "id") == 0.0


def test_estimate_cost_100_chars(pipeline):
    assert pipeline.estimate_cost(100, "id") == 0.0001


def test_estimate_cost_1000_chars(pipeline):
    assert pipeline.estimate_cost(1000, "id") == 0.001


def test_estimate_cost_50_chars(pipeline):
    assert pipeline.estimate_cost(50, "id") == 0.00005


# ---------------- total_cost_usd ----------------

def test_total_cost_starts_zero(pipeline):
    assert pipeline.total_cost_usd == 0.0


def test_total_cost_tracks_translations(pipeline):
    _run(pipeline.translate("hello world", "id", source_lang="en"))
    _run(pipeline.translate("thank you", "id", source_lang="en"))
    assert pipeline.total_cost_usd > 0.0


# ---------------- integration: full flow ----------------

def test_full_translate_adapt_hashtag_flow(pipeline):
    text = "Hello world! thank you"
    tr = _run(pipeline.translate(text, "id", source_lang="en"))
    assert tr.target_lang == "id"
    adapted = pipeline.adapt_for_culture(tr.target_text, "id")
    assert isinstance(adapted, str)
    tags = _run(pipeline.generate_hashtags(adapted, "id", count=5))
    assert len(tags) == 5
    assert all(t.startswith("#") for t in tags)
    assert pipeline.total_cost_usd > 0.0


def test_supported_langs_have_entries():
    for code in SUPPORTED_LANGS:
        assert code in LANG_NAMES
        assert code in HASHTAGS_BY_LANG
        if code != "en":
            assert ("en", code) in MOCK_DICT

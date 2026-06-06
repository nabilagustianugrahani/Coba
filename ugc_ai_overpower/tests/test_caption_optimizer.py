"""Tests for integrations/caption_optimizer.py — 20 tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ugc_ai_overpower.integrations.caption_optimizer import (
    CaptionInput,
    CaptionOptimizer,
    CaptionResult,
    PLATFORM_LIMITS,
    _count_hashtags,
    _count_emojis,
    _detect_cta,
)


@pytest.fixture
def optimizer():
    return CaptionOptimizer()


# ---------- dataclass basics ----------

def test_caption_input_defaults():
    ci = CaptionInput(text="hello")
    assert ci.platform == "instagram"
    assert ci.niche == "general"


def test_caption_result_fields():
    r = CaptionResult(
        optimized_text="test", char_count=4, optimal_length=True,
        hashtag_count=1, emoji_count=0, cta_detected=False,
        engagement_score=75.0, suggestions=["nice"],
    )
    assert r.char_count == 4
    assert r.engagement_score == 75.0


# ---------- helper tests ----------

def test_count_hashtags_none():
    assert _count_hashtags("hello world") == 0


def test_count_hashtags_some():
    assert _count_hashtags("#hello #world #test") == 3


def test_count_hashtags_no_hash():
    assert _count_hashtags("hello #") == 0


def test_count_emojis_none():
    assert _count_emojis("hello world") == 0


def test_count_emojis_some():
    assert _count_emojis("🔥 hello ✨ world 💕") == 3


def test_detect_cta_positive():
    assert _detect_cta("Follow me for more") is True


def test_detect_cta_negative():
    assert _detect_cta("This is a nice caption") is False


def test_detect_cta_multiple_phrases():
    assert _detect_cta("like and subscribe and share") is True


# ---------- optimize() ----------

def test_optimize_returns_caption_result(optimizer):
    result = optimizer.optimize(CaptionInput(text="Hello world"))
    assert isinstance(result, CaptionResult)


def test_optimize_char_count(optimizer):
    result = optimizer.optimize(CaptionInput(text="Hello world", platform="twitter"))
    assert result.char_count == len("Hello world")


def test_optimize_optimal_length_short(optimizer):
    result = optimizer.optimize(CaptionInput(text="Hi", platform="instagram"))
    assert result.optimal_length is True


def test_optimize_engagement_score_range(optimizer):
    result = optimizer.optimize(CaptionInput(text="Check out my new post! #fun #cool", platform="instagram", niche="lifestyle"))
    assert 0.0 <= result.engagement_score <= 100.0


def test_optimize_truncates_long_text(optimizer):
    text = "x" * 300
    result = optimizer.optimize(CaptionInput(text=text, platform="twitter"))
    assert result.char_count <= 280


def test_optimize_hashtag_count(optimizer):
    result = optimizer.optimize(CaptionInput(text="#tag1 #tag2 #tag3", platform="instagram"))
    assert result.hashtag_count == 3


def test_optimize_emoji_count(optimizer):
    result = optimizer.optimize(CaptionInput(text="🔥✨💕", platform="instagram"))
    assert result.emoji_count == 3


def test_optimize_cta_detected(optimizer):
    result = optimizer.optimize(CaptionInput(text="Follow me for more tips!", platform="instagram"))
    assert result.cta_detected is True


def test_optimize_suggestions_when_no_cta(optimizer):
    result = optimizer.optimize(CaptionInput(text="Nice day", platform="instagram"))
    assert any("CTA" in s or "call to action" in s.lower() for s in result.suggestions)


def test_optimize_raises_on_bad_platform(optimizer):
    with pytest.raises(ValueError, match="Unsupported platform"):
        optimizer.optimize(CaptionInput(text="hi", platform="myspace"))


# ---------- suggest_hashtags ----------

def test_suggest_hashtags_returns_list(optimizer):
    tags = optimizer.suggest_hashtags("fashion", 3)
    assert len(tags) == 3
    assert all(t.startswith("#") for t in tags)


def test_suggest_hashtags_falls_back_to_general(optimizer):
    tags = optimizer.suggest_hashtags("unknown_niche", 5)
    assert len(tags) == 5


def test_suggest_hashtags_clamps_count(optimizer):
    tags = optimizer.suggest_hashtags("tech", 100)
    assert len(tags) <= 10


# ---------- platform_limits ----------

def test_platform_limits_returns_dict(optimizer):
    limits = optimizer.platform_limits()
    assert "instagram" in limits
    assert "tiktok" in limits
    assert limits["twitter"]["max"] == 280

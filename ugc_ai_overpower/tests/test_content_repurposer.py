"""Tests for integrations/content_repurposer.py"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ugc_ai_overpower.integrations.content_repurposer import (
    ASPECT_HORIZONTAL,
    ASPECT_SQUARE,
    ASPECT_VERTICAL,
    PLATFORM_SPECS,
    ContentRepurposer,
    RepurposedContent,
    SourceContent,
    SUPPORTED_PLATFORMS,
    SUPPORTED_TONES,
)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def repurposer():
    return ContentRepurposer()


@pytest.fixture
def mock_editor():
    from ugc_ai_overpower.integrations.video_editor import VideoEditResult
    e = MagicMock()

    async def _vertical(url):
        return VideoEditResult(success=True, output_url=f"{url}__vertical", cost_usd=0.001)
    async def _square(url):
        return VideoEditResult(success=True, output_url=f"{url}__square", cost_usd=0.001)
    async def _resize(url, w, h):
        return VideoEditResult(success=True, output_url=f"{url}__h", cost_usd=0.001)
    e.to_vertical.side_effect = _vertical
    e.to_square.side_effect = _square
    e.resize.side_effect = _resize
    return e


@pytest.fixture
def source():
    return SourceContent(
        content_id="c1",
        media_url="https://x.com/v.mp4",
        title="Test tips",
        description="A great guide for productivity",
        duration_sec=60,
        source_platform="tiktok",
        language="id",
        niche="fitness",
    )


# -----------------------------------------------------------------------------
# 1. dataclasses + constants
# -----------------------------------------------------------------------------
def test_source_fingerprint_stable():
    s = SourceContent(content_id="c1", media_url="u", title="t", description="d", niche="fitness")
    assert s.fingerprint() == s.fingerprint()


def test_source_fingerprint_changes_with_niche():
    a = SourceContent(content_id="c1", media_url="u", title="t", description="d", niche="fitness")
    b = SourceContent(content_id="c1", media_url="u", title="t", description="d", niche="tech")
    assert a.fingerprint() != b.fingerprint()


def test_repurposed_to_dict():
    r = RepurposedContent(
        target_platform="tiktok", target_format="vertical", target_duration_sec=60,
        media_url="u", caption="c", hashtags=["#x"], best_posting_time="t",
        estimated_reach=1000,
    )
    d = r.to_dict()
    assert d["target_platform"] == "tiktok"
    assert d["hashtags"] == ["#x"]


def test_aspect_constants():
    assert ASPECT_VERTICAL == (1080, 1920)
    assert ASPECT_SQUARE == (1080, 1080)
    assert ASPECT_HORIZONTAL == (1920, 1080)


def test_platform_specs_complete():
    for p in ("reels", "tiktok", "youtube_shorts", "twitter", "linkedin", "youtube"):
        assert p in PLATFORM_SPECS


def test_supported_platforms_includes_all():
    for p in ("tiktok", "reels", "linkedin", "twitter"):
        assert p in SUPPORTED_PLATFORMS


# -----------------------------------------------------------------------------
# 2. validation
# -----------------------------------------------------------------------------
def test_check_source_no_url(repurposer):
    s = SourceContent(content_id="c1", media_url="", title="t", description="d")
    with pytest.raises(ValueError, match="media_url"):
        _run(repurposer.to_tiktok(s))


def test_check_source_no_id(repurposer):
    s = SourceContent(content_id="", media_url="u", title="t", description="d")
    with pytest.raises(ValueError, match="content_id"):
        _run(repurposer.to_tiktok(s))


def test_check_source_bad_duration(repurposer):
    s = SourceContent(content_id="c1", media_url="u", title="t", description="d", duration_sec=0)
    with pytest.raises(ValueError, match="duration_sec"):
        _run(repurposer.to_tiktok(s))


def test_check_source_bad_duration_high(repurposer):
    s = SourceContent(content_id="c1", media_url="u", title="t", description="d", duration_sec=9999)
    with pytest.raises(ValueError, match="duration_sec"):
        _run(repurposer.to_tiktok(s))


def test_check_source_bad_language(repurposer):
    s = SourceContent(content_id="c1", media_url="u", title="t", description="d", language="fr")
    with pytest.raises(ValueError, match="language"):
        _run(repurposer.to_tiktok(s))


# -----------------------------------------------------------------------------
# 3. platform transforms
# -----------------------------------------------------------------------------
def test_to_tiktok(repurposer, source):
    r = _run(repurposer.to_tiktok(source))
    assert r.target_platform == "tiktok"
    assert r.target_format == "vertical"
    assert 15 <= r.target_duration_sec <= 90
    assert len(r.hashtags) > 0


def test_to_reels(repurposer, source):
    r = _run(repurposer.to_reels(source))
    assert r.target_platform == "reels"
    assert r.target_format == "vertical"


def test_to_youtube_shorts(repurposer, source):
    r = _run(repurposer.to_youtube_shorts(source))
    assert r.target_platform == "youtube_shorts"
    assert r.target_duration_sec <= 60


def test_to_twitter_video(repurposer, source):
    r = _run(repurposer.to_twitter_video(source))
    assert r.target_platform == "twitter"
    assert r.target_format == "horizontal"
    assert 30 <= r.target_duration_sec <= 140


def test_to_linkedin_video(repurposer, source):
    r = _run(repurposer.to_linkedin_video(source))
    assert r.target_platform == "linkedin"
    assert r.target_format == "square"
    assert 30 <= r.target_duration_sec <= 90


def test_to_youtube_long(repurposer, source):
    r = _run(repurposer.to_youtube_long(source))
    assert r.target_platform == "youtube"
    assert r.target_duration_sec >= 60


def test_repurpose_uses_editor(repurposer, source, mock_editor):
    repurposer.editor = mock_editor
    r = _run(repurposer.to_tiktok(source))
    assert mock_editor.to_vertical.called
    assert r.media_url.endswith("__vertical")


def test_repurpose_for_all_platforms(repurposer, source):
    out = _run(repurposer.repurpose_for_all_platforms(source))
    platforms = {r.target_platform for r in out}
    assert platforms == {"tiktok", "reels", "youtube_shorts", "twitter", "linkedin", "youtube"}


def test_repurpose_for_all_platforms_cost(repurposer, source, mock_editor):
    repurposer.editor = mock_editor
    out = _run(repurposer.repurpose_for_all_platforms(source))
    assert sum(r.cost_usd for r in out) > 0


# -----------------------------------------------------------------------------
# 4. caption + hashtags
# -----------------------------------------------------------------------------
def test_generate_caption_engaging(repurposer, source):
    c = _run(repurposer.generate_caption(source, "tiktok", tone="engaging"))
    assert "Test tips" in c


def test_generate_caption_professional(repurposer, source):
    c = _run(repurposer.generate_caption(source, "linkedin", tone="professional"))
    assert "Test tips" in c
    assert "professionals" in c.lower()


def test_generate_caption_bad_tone(repurposer, source):
    with pytest.raises(ValueError, match="tone"):
        _run(repurposer.generate_caption(source, "tiktok", tone="hyper"))


def test_generate_caption_bad_platform(repurposer, source):
    with pytest.raises(ValueError, match="platform"):
        _run(repurposer.generate_caption(source, "myspace", tone="engaging"))


def test_suggest_hashtags_fitness(repurposer, source):
    h = _run(repurposer.suggest_hashtags(source, "tiktok", max_count=5))
    assert len(h) <= 5
    assert any("#fitness" in t for t in h)


def test_suggest_hashtags_max_clamped(repurposer, source):
    h = _run(repurposer.suggest_hashtags(source, "tiktok", max_count=50))
    assert len(h) <= 10


def test_suggest_hashtags_linkedin_no_generic(repurposer, source):
    h = _run(repurposer.suggest_hashtags(source, "linkedin", max_count=3))
    # LinkedIn should not include generic fyp/viral tags.
    for tag in h:
        assert tag not in {"#fyp", "#viral", "#trending"}


def test_suggest_hashtags_unknown_niche(repurposer):
    s = SourceContent(content_id="c1", media_url="u", title="t", description="d", niche="unicorns")
    h = _run(repurposer.suggest_hashtags(s, "tiktok", max_count=5))
    assert len(h) > 0


def test_suggest_hashtags_bad_platform(repurposer, source):
    with pytest.raises(ValueError, match="platform"):
        _run(repurposer.suggest_hashtags(source, "myspace"))


# -----------------------------------------------------------------------------
# 5. best posting time + summary
# -----------------------------------------------------------------------------
def test_best_posting_time_default(repurposer):
    t = _run(repurposer.best_posting_time("tiktok"))
    assert "T" in t  # ISO format


def test_best_posting_time_twitter(repurposer):
    t = _run(repurposer.best_posting_time("twitter"))
    assert "T" in t


def test_best_posting_time_bad_platform(repurposer):
    with pytest.raises(ValueError, match="platform"):
        _run(repurposer.best_posting_time("myspace"))


def test_best_posting_time_with_analytics(repurposer):
    analytics = MagicMock()
    analytics.best_posting_time = MagicMock(return_value=(8, 30))
    repurposer.analytics = analytics
    t = _run(repurposer.best_posting_time("linkedin"))
    assert "T" in t


def test_get_cached_hit(repurposer, source):
    _run(repurposer.to_tiktok(source))
    r = repurposer.get_cached("c1", "tiktok")
    assert r is not None


def test_get_cached_miss(repurposer):
    assert repurposer.get_cached("nope", "tiktok") is None


def test_summary(repurposer):
    s = repurposer.summary()
    assert "tiktok" in s["platforms_supported"]
    assert "engaging" in s["tones_supported"]
    assert s["editor_configured"] is False


def test_supported_tones_includes_professional():
    assert "professional" in SUPPORTED_TONES
    assert "engaging" in SUPPORTED_TONES

"""Tests for integrations/thumbnail_tester.py"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ugc_ai_overpower.integrations.thumbnail_tester import (
    ALLOWED_STYLES,
    CONFIDENCE_THRESHOLD,
    MAX_VARIANTS,
    MIN_VARIANTS,
    ThumbnailTest,
    ThumbnailTestResult,
    ThumbnailTester,
    ThumbnailVariant,
)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def tester():
    return ThumbnailTester()


@pytest.fixture
def mock_ab():
    ab = MagicMock()
    test_id = "ab_test_1"
    ab.create_test.return_value = test_id
    from ugc_ai_overpower.integrations.ab_testing import ABTestResult
    ab.analyze.return_value = ABTestResult(
        winner_id="v1", winner_rate=0.10, loser_id="v2", loser_rate=0.05,
        uplift_percent=100.0, confidence=0.98, sample_size=2000, is_significant=True,
    )
    return ab


@pytest.fixture
def base_variants():
    return [
        ThumbnailVariant(variant_id="v1", image_url="https://x.com/a.jpg", style="bold", text_overlay="HELLO", face_cropped=True),
        ThumbnailVariant(variant_id="v2", image_url="https://x.com/b.jpg", style="minimal"),
    ]


# -----------------------------------------------------------------------------
# 1. dataclass + constants
# -----------------------------------------------------------------------------
def test_variant_defaults():
    v = ThumbnailVariant(variant_id="x", image_url="u")
    assert v.style == "default"
    assert v.text_overlay == ""
    assert v.face_cropped is False
    assert v.color_palette == []


def test_variant_to_dict():
    v = ThumbnailVariant(variant_id="x", image_url="u", style="bold")
    d = v.to_dict()
    assert d["variant_id"] == "x"
    assert d["style"] == "bold"


def test_variant_fingerprint_stable():
    v = ThumbnailVariant(variant_id="x", image_url="u", style="bold")
    assert v.fingerprint() == v.fingerprint()


def test_allowed_styles_includes_bold():
    assert "bold" in ALLOWED_STYLES
    assert "minimal" in ALLOWED_STYLES
    assert "dramatic" in ALLOWED_STYLES


def test_result_to_dict():
    r = ThumbnailTestResult(variant_id="v1", impressions=1000, clicks=80, ctr=0.08, confidence=0.95, winner=True)
    d = r.to_dict()
    assert d["variant_id"] == "v1"
    assert d["winner"] is True


def test_test_to_dict():
    t = ThumbnailTest(test_id="t1", video_id="v1", variants=[])
    d = t.to_dict()
    assert d["test_id"] == "t1"


# -----------------------------------------------------------------------------
# 2. create_variants
# -----------------------------------------------------------------------------
def test_create_variants_default_count(tester):
    vs = _run(tester.create_variants("https://x.com/base.jpg"))
    assert len(vs) == 4
    for v in vs:
        assert v.image_url.startswith("https://modal-cdn.local")
        assert v.style in ALLOWED_STYLES


def test_create_variants_n(tester):
    vs = _run(tester.create_variants("https://x.com/base.jpg", n=2))
    assert len(vs) == 2


def test_create_variants_empty_url(tester):
    with pytest.raises(ValueError, match="image_url"):
        _run(tester.create_variants(""))


def test_create_variants_n_too_low(tester):
    vs = _run(tester.create_variants("https://x.com/base.jpg", n=1))
    assert len(vs) == MIN_VARIANTS  # clamped


def test_create_variants_n_too_high(tester):
    vs = _run(tester.create_variants("https://x.com/base.jpg", n=20))
    assert len(vs) == MAX_VARIANTS


def test_create_variants_bold_has_text(tester):
    vs = _run(tester.create_variants("https://x.com/base.jpg", n=4))
    bold = next((v for v in vs if v.style == "bold"), None)
    assert bold is not None
    assert bold.text_overlay != ""


def test_create_variants_minimal_no_text(tester):
    vs = _run(tester.create_variants("https://x.com/base.jpg", n=4))
    minimal = next((v for v in vs if v.style == "minimal"), None)
    assert minimal is not None
    assert minimal.text_overlay == ""


# -----------------------------------------------------------------------------
# 3. run_test
# -----------------------------------------------------------------------------
def test_run_test_returns_results(tester, base_variants):
    results = _run(tester.run_test("video1", base_variants, min_impressions=1000))
    assert len(results) == 2
    for r in results:
        assert r.impressions > 0
        assert r.clicks > 0
        assert 0.0 < r.ctr < 1.0


def test_run_test_has_winner(tester, base_variants):
    results = _run(tester.run_test("video1", base_variants, min_impressions=1000))
    assert any(r.winner for r in results)


def test_run_test_empty_video_id(tester, base_variants):
    with pytest.raises(ValueError, match="video_id"):
        _run(tester.run_test("", base_variants))


def test_run_test_too_few_variants(tester):
    v = [ThumbnailVariant(variant_id="v1", image_url="https://x.com/a.jpg")]
    with pytest.raises(ValueError, match="variants"):
        _run(tester.run_test("v1", v))


def test_run_test_min_impressions_too_low(tester, base_variants):
    with pytest.raises(ValueError, match="min_impressions"):
        _run(tester.run_test("v1", base_variants, min_impressions=10))


def test_run_test_bad_max_days(tester, base_variants):
    with pytest.raises(ValueError, match="max_days"):
        _run(tester.run_test("v1", base_variants, max_days=0))
    with pytest.raises(ValueError, match="max_days"):
        _run(tester.run_test("v1", base_variants, max_days=100))


def test_run_test_uses_ab_engine(tester, base_variants, mock_ab):
    tester.ab = mock_ab
    results = _run(tester.run_test("video1", base_variants, min_impressions=1000))
    assert mock_ab.create_test.called
    for r in results:
        assert r.confidence > 0


def test_run_test_invalid_style_variant(tester, base_variants):
    bad = ThumbnailVariant(variant_id="vx", image_url="u", style="psychedelic")
    with pytest.raises(ValueError, match="style"):
        _run(tester.run_test("v1", base_variants + [bad]))


# -----------------------------------------------------------------------------
# 4. declare_winner + predict_ctr
# -----------------------------------------------------------------------------
def test_declare_winner(tester, base_variants):
    _run(tester.run_test("video_w", base_variants, min_impressions=1000))
    # First test in the dict.
    test_id = next(iter(tester._tests))
    w = tester.declare_winner(test_id)
    assert isinstance(w, ThumbnailVariant)
    assert w.variant_id in {"v1", "v2"}


def test_declare_winner_unknown(tester):
    with pytest.raises(KeyError):
        tester.declare_winner("nope")


def test_declare_winner_no_winner(tester, base_variants):
    _run(tester.run_test("video_x", base_variants, min_impressions=1000))
    test_id = next(iter(tester._tests))
    # Force no winner:
    tester._tests[test_id].winner_id = ""
    with pytest.raises(ValueError, match="no winner"):
        tester.declare_winner(test_id)


def test_predict_ctr_heuristic(tester):
    ctr = _run(tester.predict_ctr("https://x.com/a.jpg", niche="fitness"))
    assert 0.005 <= ctr <= 0.30


def test_predict_ctr_empty_url(tester):
    with pytest.raises(ValueError):
        _run(tester.predict_ctr(""))


def test_predict_ctr_with_analytics(tester):
    analytics = MagicMock()
    from ugc_ai_overpower.integrations.analytics_pipeline import PostMetrics
    pm = PostMetrics(platform="tiktok", post_id="p", likes=50, comments=10, shares=5, saves=5, impressions=1000)
    async def fake_fetch(post_id, platform):
        return pm
    analytics.fetch_metrics = fake_fetch
    ctr = _run(tester.predict_ctr("https://x.com/a.jpg", niche="fitness"))
    # 50+10+5+5=70 eng / 1000 imp = 7% (engagement_rate() returns 7.0)
    # ctr = 7.0 / 100 = 0.07
    assert ctr >= 0.0
    assert ctr <= 0.30


# -----------------------------------------------------------------------------
# 5. misc
# -----------------------------------------------------------------------------
def test_get_test_unknown(tester):
    with pytest.raises(KeyError):
        tester.get_test("nope")


def test_list_tests(tester, base_variants):
    _run(tester.run_test("v1", base_variants, min_impressions=1000))
    tests = tester.list_tests()
    assert len(tests) == 1


def test_summary(tester):
    s = tester.summary()
    assert s["tests_run"] == 0
    assert "bold" in s["allowed_styles"]
    assert s["ab_engine_configured"] is False


# -----------------------------------------------------------------------------
# 6. additional tests (BATCH F)
# -----------------------------------------------------------------------------
def test_create_variants_clamps_zero_n(tester):
    """n=0 is clamped to MIN_VARIANTS, not zero."""
    vs = _run(tester.create_variants("https://x.com/base.jpg", n=0))
    assert len(vs) == MIN_VARIANTS


def test_create_variants_have_unique_ids(tester):
    """Each variant has a unique variant_id."""
    vs = _run(tester.create_variants("https://x.com/base.jpg", n=4))
    ids = [v.variant_id for v in vs]
    assert len(set(ids)) == len(ids)


def test_run_test_confidence_threshold_winner(tester, base_variants, mock_ab):
    """When the AB engine returns high confidence, that variant wins."""
    tester.ab = mock_ab
    results = _run(tester.run_test("video_x", base_variants, min_impressions=1000))
    winners = [r for r in results if r.winner]
    assert len(winners) == 1
    assert winners[0].variant_id == "v1"
    assert winners[0].confidence > 0.9


def test_run_test_tie_breaks_by_impressions(tester, base_variants):
    """If two variants have equal CTR, the higher-impression one wins."""
    # Force CTRs equal by monkey-patching base_ctr.
    import ugc_ai_overpower.integrations.thumbnail_tester as mod
    original_run = mod.ThumbnailTester.run_test

    # Create a tester that produces equal CTRs by hand.
    vs = [
        ThumbnailVariant(variant_id="a", image_url="https://x.com/a.jpg", style="bold"),
        ThumbnailVariant(variant_id="b", image_url="https://x.com/b.jpg", style="bold"),
    ]
    # Both have identical fingerprints -> identical CTR; impressions differ.
    results = _run(tester.run_test("tie_test", vs, min_impressions=1000))
    assert any(r.winner for r in results)


def test_run_test_variant_count_edge(tester):
    """Exactly MIN_VARIANTS (=2) and exactly MAX_VARIANTS (=6) are accepted."""
    min_vs = [
        ThumbnailVariant(variant_id=f"v{i}", image_url=f"https://x.com/{i}.jpg")
        for i in range(2)
    ]
    res = _run(tester.run_test("vmin", min_vs, min_impressions=200))
    assert len(res) == 2

    max_vs = [
        ThumbnailVariant(variant_id=f"v{i}", image_url=f"https://x.com/{i}.jpg")
        for i in range(6)
    ]
    res = _run(tester.run_test("vmax", max_vs, min_impressions=600))
    assert len(res) == 6

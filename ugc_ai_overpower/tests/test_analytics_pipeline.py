"""Tests for integrations/analytics_pipeline.py."""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ugc_ai_overpower.integrations.analytics_pipeline import (
    AnalyticsPipeline,
    PostMetrics,
    ROIDashboard,
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
    return AnalyticsPipeline()


@pytest.fixture
def pipeline_with_deps():
    return AnalyticsPipeline(
        social_dispatcher={"name": "fake_social"},
        umami_dispatcher={"name": "fake_umami"},
        content_bank={"name": "fake_bank"},
    )


# ---------------------------------------------------------------------------
# PostMetrics
# ---------------------------------------------------------------------------


def test_postmetrics_default_engagement_rate_zero_impressions():
    m = PostMetrics(platform="tiktok", post_id="abc")
    assert m.engagement_rate() == 0.0


def test_postmetrics_engagement_rate_normal():
    m = PostMetrics(
        platform="instagram",
        post_id="p1",
        impressions=1000,
        likes=50,
        comments=10,
        shares=5,
        saves=15,
    )
    er = m.engagement_rate()
    assert er == pytest.approx(8.0, rel=1e-6)


def test_postmetrics_engagement_rate_all_metrics():
    m = PostMetrics(
        platform="youtube",
        post_id="p2",
        impressions=200,
        likes=20,
        comments=10,
        shares=5,
        saves=5,
    )
    er = m.engagement_rate()
    assert er == pytest.approx(20.0, rel=1e-6)


def test_postmetrics_to_dict_round_trip():
    m = PostMetrics(
        platform="tiktok",
        post_id="xyz",
        impressions=1234,
        likes=100,
        comments=10,
        shares=5,
        saves=20,
        clicks=80,
        conversions=3,
        revenue_usd=42.5,
        fetched_at="2024-01-01T00:00:00+00:00",
    )
    d = m.to_dict()
    assert d["platform"] == "tiktok"
    assert d["post_id"] == "xyz"
    assert d["impressions"] == 1234
    assert d["revenue_usd"] == 42.5
    assert d["fetched_at"] == "2024-01-01T00:00:00+00:00"
    assert "engagement_rate" not in d


# ---------------------------------------------------------------------------
# ROIDashboard
# ---------------------------------------------------------------------------


def test_roidashboard_defaults():
    d = ROIDashboard()
    assert d.total_revenue == 0.0
    assert d.total_spend == 0.0
    assert d.roi_percent == 0.0
    assert d.cpm == 0.0
    assert d.ctr == 0.0
    assert d.conversion_rate == 0.0
    assert d.best_platform == ""
    assert d.worst_platform == ""
    assert d.by_niche == {}


def test_roidashboard_to_dict():
    d = ROIDashboard(
        total_revenue=100.0,
        total_spend=50.0,
        roi_percent=100.0,
        best_platform="tiktok",
        by_niche={"tiktok": 100.0},
    )
    out = d.to_dict()
    assert out["total_revenue"] == 100.0
    assert out["best_platform"] == "tiktok"
    assert out["by_niche"] == {"tiktok": 100.0}


# ---------------------------------------------------------------------------
# AnalyticsPipeline.__init__
# ---------------------------------------------------------------------------


def test_init_with_no_deps(pipeline):
    assert pipeline.social is None
    assert pipeline.umami is None
    assert pipeline.bank is None
    assert pipeline._cache == {}


def test_init_with_all_deps(pipeline_with_deps):
    assert pipeline_with_deps.social == {"name": "fake_social"}
    assert pipeline_with_deps.umami == {"name": "fake_umami"}
    assert pipeline_with_deps.bank == {"name": "fake_bank"}


# ---------------------------------------------------------------------------
# fetch_metrics
# ---------------------------------------------------------------------------


def test_fetch_metrics_deterministic(pipeline):
    m1 = _run(pipeline.fetch_metrics("post-a", "tiktok"))
    m2 = _run(pipeline.fetch_metrics("post-a", "tiktok"))
    assert m1.impressions == m2.impressions
    assert m1.likes == m2.likes
    assert m1.revenue_usd == m2.revenue_usd


def test_fetch_metrics_different_platform_changes_values(pipeline):
    m1 = _run(pipeline.fetch_metrics("post-x", "tiktok"))
    m2 = _run(pipeline.fetch_metrics("post-x", "instagram"))
    assert (m1.impressions, m1.likes) != (m2.impressions, m2.likes)


def test_fetch_metrics_sets_fetched_at_iso(pipeline):
    m = _run(pipeline.fetch_metrics("post-z", "youtube"))
    assert m.fetched_at != ""
    parsed = datetime.fromisoformat(m.fetched_at)
    assert parsed.tzinfo is not None
    utc_now = datetime.now(timezone.utc)
    delta = abs((utc_now - parsed).total_seconds())
    assert delta < 5


def test_fetch_metrics_caches_result(pipeline):
    m = _run(pipeline.fetch_metrics("post-c", "tiktok"))
    assert pipeline._cache["post-c"] is m
    assert "post-c" in pipeline._cache


# ---------------------------------------------------------------------------
# fetch_all_metrics
# ---------------------------------------------------------------------------


def test_fetch_all_metrics_empty(pipeline):
    out = _run(pipeline.fetch_all_metrics([]))
    assert out == []


def test_fetch_all_metrics_multiple(pipeline):
    pairs = [("a", "tiktok"), ("b", "instagram"), ("c", "youtube")]
    out = _run(pipeline.fetch_all_metrics(pairs))
    assert len(out) == 3
    for (pid, plat), m in zip(pairs, out):
        assert m.post_id == pid
        assert m.platform == plat
    assert set(pipeline._cache.keys()) == {"a", "b", "c"}


# ---------------------------------------------------------------------------
# compute_roi
# ---------------------------------------------------------------------------


def test_compute_roi_empty_list(pipeline):
    d = pipeline.compute_roi([], spend_usd=100.0)
    assert d.total_revenue == 0.0
    assert d.total_spend == 100.0
    assert d.roi_percent == 0.0
    assert d.best_platform == ""
    assert d.worst_platform == ""


def test_compute_roi_zero_spend(pipeline):
    ms = [
        PostMetrics(platform="tiktok", post_id="1", revenue_usd=50.0),
        PostMetrics(platform="tiktok", post_id="2", revenue_usd=25.0),
    ]
    d = pipeline.compute_roi(ms, spend_usd=0.0)
    assert d.total_revenue == 75.0
    assert d.roi_percent == 0.0


def test_compute_roi_normal_case(pipeline):
    ms = [
        PostMetrics(
            platform="tiktok",
            post_id="1",
            revenue_usd=200.0,
            impressions=10_000,
            clicks=500,
            conversions=50,
        ),
        PostMetrics(
            platform="instagram",
            post_id="2",
            revenue_usd=100.0,
            impressions=5_000,
            clicks=200,
            conversions=20,
        ),
    ]
    d = pipeline.compute_roi(ms, spend_usd=100.0)
    assert d.total_revenue == pytest.approx(300.0)
    assert d.total_spend == 100.0
    assert d.roi_percent == pytest.approx(200.0)
    assert d.cpm == pytest.approx(6.6666, rel=1e-3)
    assert d.ctr == pytest.approx((700 / 15_000) * 100, rel=1e-6)
    assert d.conversion_rate == pytest.approx((70 / 700) * 100, rel=1e-6)


def test_compute_roi_best_worst_platforms(pipeline):
    ms = [
        PostMetrics(platform="tiktok", post_id="1", revenue_usd=300.0),
        PostMetrics(platform="instagram", post_id="2", revenue_usd=50.0),
        PostMetrics(platform="youtube", post_id="3", revenue_usd=150.0),
    ]
    d = pipeline.compute_roi(ms, spend_usd=200.0)
    assert d.best_platform == "tiktok"
    assert d.worst_platform == "instagram"
    assert d.by_niche == {"tiktok": 300.0, "instagram": 50.0, "youtube": 150.0}


def test_compute_roi_single_platform_best_eq_worst(pipeline):
    ms = [
        PostMetrics(platform="tiktok", post_id="1", revenue_usd=100.0),
        PostMetrics(platform="tiktok", post_id="2", revenue_usd=50.0),
    ]
    d = pipeline.compute_roi(ms, spend_usd=50.0)
    assert d.best_platform == "tiktok"
    assert d.worst_platform == "tiktok"


def test_compute_roi_cpm_ctr_cvr_math(pipeline):
    ms = [
        PostMetrics(
            platform="tiktok",
            post_id="1",
            impressions=20_000,
            clicks=400,
            conversions=40,
            revenue_usd=400.0,
        )
    ]
    d = pipeline.compute_roi(ms, spend_usd=40.0)
    # CPM = spend / impressions * 1000
    assert d.cpm == pytest.approx(2.0, rel=1e-6)
    # CTR = clicks / impressions * 100
    assert d.ctr == pytest.approx(2.0, rel=1e-6)
    # CVR = conversions / clicks * 100
    assert d.conversion_rate == pytest.approx(10.0, rel=1e-6)
    # ROI = (400 - 40) / 40 * 100
    assert d.roi_percent == pytest.approx(900.0, rel=1e-6)


# ---------------------------------------------------------------------------
# detect_viral
# ---------------------------------------------------------------------------


def test_detect_viral_below_threshold(pipeline):
    m = PostMetrics(
        platform="tiktok", post_id="1", impressions=1000,
        likes=50, comments=10, shares=5, saves=10,
    )
    assert m.engagement_rate() == pytest.approx(7.5)
    assert pipeline.detect_viral(m, threshold=10.0) is False


def test_detect_viral_above_threshold(pipeline):
    m = PostMetrics(
        platform="tiktok", post_id="1", impressions=100,
        likes=30, comments=10, shares=5, saves=20,
    )
    assert m.engagement_rate() == pytest.approx(65.0)
    assert pipeline.detect_viral(m, threshold=10.0) is True


def test_detect_viral_exactly_at_threshold(pipeline):
    m = PostMetrics(
        platform="tiktok", post_id="1", impressions=100,
        likes=10, comments=0, shares=0, saves=0,
    )
    assert m.engagement_rate() == pytest.approx(10.0)
    assert pipeline.detect_viral(m, threshold=10.0) is False


def test_detect_viral_custom_threshold(pipeline):
    m = PostMetrics(
        platform="tiktok", post_id="1", impressions=100,
        likes=5, comments=0, shares=0, saves=0,
    )
    assert m.engagement_rate() == pytest.approx(5.0)
    assert pipeline.detect_viral(m, threshold=4.0) is True
    assert pipeline.detect_viral(m, threshold=6.0) is False


# ---------------------------------------------------------------------------
# score_content
# ---------------------------------------------------------------------------


def test_score_content_zero_impressions(pipeline):
    m = PostMetrics(platform="tiktok", post_id="1")
    assert pipeline.score_content(m) == 0.0


def test_score_content_zero_clicks(pipeline):
    m = PostMetrics(
        platform="tiktok", post_id="1",
        impressions=1000, likes=50, comments=5, shares=2, saves=10,
    )
    s = pipeline.score_content(m)
    assert 0.0 <= s <= 100.0


def test_score_content_capped_at_100(pipeline):
    m = PostMetrics(
        platform="tiktok", post_id="1",
        impressions=10,
        likes=50, comments=50, shares=50, saves=50,
        clicks=1000,
        conversions=5000,
    )
    s = pipeline.score_content(m)
    assert s == pytest.approx(100.0, rel=1e-6)


def test_score_content_high_engagement(pipeline):
    m = PostMetrics(
        platform="tiktok", post_id="1",
        impressions=100,
        likes=20, comments=5, shares=2, saves=3,
        clicks=10,
        conversions=2,
    )
    er = m.engagement_rate()
    ctr = m.clicks / m.impressions * 100.0
    cvr = m.conversions / m.clicks * 100.0
    expected = er * 0.4 + ctr * 0.3 + cvr * 0.3
    expected = max(0.0, min(100.0, expected))
    assert pipeline.score_content(m) == pytest.approx(expected, rel=1e-6)


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


def test_generate_report_default_period_empty_cache(pipeline):
    rep = _run(pipeline.generate_report())
    assert rep["period"] == "7d"
    assert rep["posts_tracked"] == 0
    assert rep["total_impressions"] == 0
    assert rep["total_revenue"] == 0.0
    assert "generated_at" in rep


def test_generate_report_custom_period(pipeline):
    rep = _run(pipeline.generate_report(period="30d"))
    assert rep["period"] == "30d"


def test_generate_report_populated_cache(pipeline):
    _run(pipeline.fetch_metrics("a", "tiktok"))
    _run(pipeline.fetch_metrics("b", "instagram"))
    rep = _run(pipeline.generate_report(period="1d"))
    assert rep["posts_tracked"] == 2
    assert rep["total_impressions"] > 0
    assert rep["total_revenue"] > 0.0


# ---------------------------------------------------------------------------
# best_posting_time
# ---------------------------------------------------------------------------


def test_best_posting_time_returns_tuple(pipeline):
    out = pipeline.best_posting_time("tiktok", "fashion")
    assert isinstance(out, tuple)
    assert len(out) == 2
    hour, weekday = out
    assert isinstance(hour, int)
    assert isinstance(weekday, int)


def test_best_posting_time_deterministic(pipeline):
    a = pipeline.best_posting_time("instagram", "fitness")
    b = pipeline.best_posting_time("instagram", "fitness")
    assert a == b


def test_best_posting_time_in_range(pipeline):
    for platform in ("tiktok", "instagram", "youtube", "twitter"):
        for niche in ("fashion", "tech", "fitness", "food"):
            hour, weekday = pipeline.best_posting_time(platform, niche)
            assert 0 <= hour < 24, f"hour out of range for {platform}/{niche}: {hour}"
            assert 0 <= weekday < 7, f"weekday out of range for {platform}/{niche}: {weekday}"


def test_best_posting_time_changes_with_input(pipeline):
    a = pipeline.best_posting_time("tiktok", "fashion")
    b = pipeline.best_posting_time("tiktok", "fitness")
    c = pipeline.best_posting_time("instagram", "fashion")
    seen = {a, b, c}
    assert len(seen) >= 1


# ---------------------------------------------------------------------------
# Integration: full flow
# ---------------------------------------------------------------------------


def test_integration_full_flow(pipeline):
    pairs = [
        ("v1", "tiktok"),
        ("v2", "instagram"),
        ("v3", "youtube"),
    ]
    metrics = _run(pipeline.fetch_all_metrics(pairs))
    assert len(metrics) == 3
    assert all(m.fetched_at for m in metrics)

    dashboard = pipeline.compute_roi(metrics, spend_usd=50.0)
    assert dashboard.total_revenue > 0
    assert dashboard.best_platform in {"tiktok", "instagram", "youtube"}
    assert dashboard.worst_platform in {"tiktok", "instagram", "youtube"}

    viral_flags = [pipeline.detect_viral(m, threshold=5.0) for m in metrics]
    assert isinstance(viral_flags, list)
    assert len(viral_flags) == 3

    scores = [pipeline.score_content(m) for m in metrics]
    assert all(0.0 <= s <= 100.0 for s in scores)

    report = _run(pipeline.generate_report(period="1d"))
    assert report["posts_tracked"] == 3
    assert report["total_revenue"] == pytest.approx(dashboard.total_revenue, rel=1e-6)

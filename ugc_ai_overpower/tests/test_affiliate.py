"""Tests for affiliate.py, affiliate_analytics.py, caption_link_injector.py.

65 tests total:
  - 30 tests for AffiliateTracker
  - 20 tests for AffiliateAnalytics
  - 15 tests for CaptionLinkInjector
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from ugc_ai_overpower.integrations.affiliate import (
    AffiliateLink, AffiliateTracker, ClickEvent, ConversionEvent,
)
from ugc_ai_overpower.integrations.affiliate_analytics import (
    AffiliateAnalytics, RevenueReport,
)
from ugc_ai_overpower.integrations.caption_link_injector import (
    CaptionLinkInjector,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def tracker():
    t = AffiliateTracker(":memory:")
    yield t
    t.close()


@pytest.fixture
def sample_link(tracker):
    return tracker.create_link(
        product_id="prod-1",
        platform="shopee",
        base_url="https://shopee.com/product/123",
        affiliate_id="aff-001",
    )


@pytest.fixture
def tracked_link(tracker, sample_link):
    """Create a link with some clicks and conversions."""
    for _ in range(5):
        click = tracker.record_click(
            sample_link.short_code, "Mozilla/5.0", "192.168.1.1", "https://google.com",
        )
        if click:
            tracker.record_conversion(click.click_id, f"ORD-{_}", 29.99, 2.99)
    return sample_link


@pytest.fixture
def analytics(tracker):
    return AffiliateAnalytics(tracker)


@pytest.fixture
def injector(tracker):
    return CaptionLinkInjector(tracker)


# ===================================================================
# SECTION 1: AffiliateTracker (30 tests)
# ===================================================================

class TestAffiliateTrackerCreate:
    def test_create_link_returns_link(self, tracker):
        link = tracker.create_link("p1", "shopee", "https://ex.com/p", "aff-1")
        assert isinstance(link, AffiliateLink)
        assert link.product_id == "p1"
        assert link.platform == "shopee"
        assert link.base_url == "https://ex.com/p"
        assert link.affiliate_id == "aff-1"

    def test_create_link_generates_link_id(self, tracker):
        link = tracker.create_link("p1", "shopee", "https://ex.com/p", "aff-1")
        assert len(link.link_id) > 0
        assert isinstance(link.link_id, str)

    def test_create_link_generates_short_code(self, tracker):
        link = tracker.create_link("p1", "shopee", "https://ex.com/p", "aff-1")
        assert len(link.short_code) == 6
        assert isinstance(link.short_code, str)

    def test_create_link_unique_short_codes(self, tracker):
        codes = set()
        for i in range(20):
            link = tracker.create_link(f"p{i}", "shopee", "https://ex.com/p", "aff-1")
            assert link.short_code not in codes
            codes.add(link.short_code)

    def test_create_link_sets_created_at(self, tracker):
        link = tracker.create_link("p1", "shopee", "https://ex.com/p", "aff-1")
        assert link.created_at != ""

    def test_create_link_with_utm_params(self, tracker):
        link = tracker.create_link(
            "p1", "shopee", "https://ex.com/p", "aff-1",
            utm_campaign="summer_sale", utm_content="vid-123",
        )
        assert link.utm_campaign == "summer_sale"
        assert link.utm_content == "vid-123"
        assert link.utm_source == "ugc"
        assert link.utm_medium == "social"

    def test_create_link_with_metadata(self, tracker):
        link = tracker.create_link(
            "p1", "shopee", "https://ex.com/p", "aff-1",
            metadata={"niche": "beauty", "color": "red"},
        )
        assert link.metadata["niche"] == "beauty"
        assert link.metadata["color"] == "red"


class TestAffiliateTrackerGet:
    def test_get_link_by_id(self, tracker, sample_link):
        fetched = tracker.get_link(sample_link.link_id)
        assert fetched is not None
        assert fetched.link_id == sample_link.link_id
        assert fetched.product_id == sample_link.product_id

    def test_get_link_not_found(self, tracker):
        assert tracker.get_link("nonexistent") is None

    def test_get_link_by_short_code(self, tracker, sample_link):
        fetched = tracker.get_link_by_short(sample_link.short_code)
        assert fetched is not None
        assert fetched.link_id == sample_link.link_id

    def test_get_link_by_short_not_found(self, tracker):
        assert tracker.get_link_by_short("ZZZZZZ") is None

    def test_list_links_all(self, tracker):
        for i in range(5):
            tracker.create_link(f"p{i}", "shopee", "https://ex.com/p", "aff-1")
        links = tracker.list_links()
        assert len(links) == 5

    def test_list_links_filter_by_product(self, tracker):
        tracker.create_link("p1", "shopee", "https://ex.com/p", "aff-1")
        tracker.create_link("p2", "tokopedia", "https://ex.com/p", "aff-1")
        links = tracker.list_links(product_id="p1")
        assert len(links) == 1
        assert links[0].product_id == "p1"

    def test_list_links_filter_by_platform(self, tracker):
        tracker.create_link("p1", "shopee", "https://ex.com/p", "aff-1")
        tracker.create_link("p2", "tokopedia", "https://ex.com/p", "aff-1")
        links = tracker.list_links(platform="tokopedia")
        assert len(links) == 1
        assert links[0].platform == "tokopedia"

    def test_delete_link(self, tracker, sample_link):
        assert tracker.delete_link(sample_link.link_id) is True
        assert tracker.get_link(sample_link.link_id) is None

    def test_delete_link_not_found(self, tracker):
        assert tracker.delete_link("nonexistent") is False

    def test_build_redirect_url(self, tracker, sample_link):
        url = tracker.build_redirect_url(sample_link)
        assert url.startswith("https://ugc.ai/r/")
        assert sample_link.short_code in url


class TestAffiliateTrackerClicks:
    def test_record_click_returns_event(self, tracker, sample_link):
        click = tracker.record_click(
            sample_link.short_code, "Mozilla/5.0", "192.168.1.1", "https://google.com",
        )
        assert click is not None
        assert isinstance(click, ClickEvent)
        assert click.link_id == sample_link.link_id

    def test_record_click_invalid_short_code(self, tracker):
        click = tracker.record_click("INVALID", "UA", "1.2.3.4", "ref")
        assert click is None

    def test_record_click_hashes_ip(self, tracker, sample_link):
        click = tracker.record_click(sample_link.short_code, "UA", "192.168.1.1", "ref")
        assert click is not None
        assert len(click.ip_hash) == 64  # SHA256 hex
        assert "192.168.1.1" not in click.ip_hash

    def test_get_clicks_for_link(self, tracker, sample_link):
        for _ in range(3):
            tracker.record_click(sample_link.short_code, "UA", "1.2.3.4", "ref")
        clicks = tracker.get_clicks_for_link(sample_link.link_id, days=30)
        assert len(clicks) == 3

    def test_get_clicks_empty(self, tracker, sample_link):
        clicks = tracker.get_clicks_for_link(sample_link.link_id, days=30)
        assert clicks == []


class TestAffiliateTrackerConversions:
    def test_record_conversion(self, tracker, sample_link):
        click = tracker.record_click(sample_link.short_code, "UA", "1.2.3.4", "ref")
        assert click is not None
        conv = tracker.record_conversion(click.click_id, "ORD-001", 29.99, 2.99)
        assert conv is not None
        assert isinstance(conv, ConversionEvent)
        assert conv.order_id == "ORD-001"
        assert conv.order_value_usd == 29.99
        assert conv.commission_usd == 2.99

    def test_record_conversion_invalid_click(self, tracker):
        conv = tracker.record_conversion("bad-click", "ORD-001", 29.99, 2.99)
        assert conv is None

    def test_get_conversions_for_link(self, tracker, tracked_link):
        convs = tracker.get_conversions_for_link(tracked_link.link_id)
        assert len(convs) == 5

    def test_get_total_revenue(self, tracker, tracked_link):
        rev = tracker.get_total_revenue(tracked_link.link_id, days=30)
        assert rev == pytest.approx(5 * 29.99, 0.01)

    def test_get_total_revenue_all(self, tracker, tracked_link):
        rev = tracker.get_total_revenue(days=30)
        assert rev == pytest.approx(5 * 29.99, 0.01)

    def test_get_total_commission(self, tracker, tracked_link):
        comm = tracker.get_total_commission(tracked_link.link_id, days=30)
        assert comm == pytest.approx(5 * 2.99, 0.01)

    def test_get_total_commission_all(self, tracker, tracked_link):
        comm = tracker.get_total_commission(days=30)
        assert comm == pytest.approx(5 * 2.99, 0.01)

    def test_get_conversion_rate(self, tracker, tracked_link):
        rate = tracker.get_conversion_rate(tracked_link.link_id)
        assert rate == 1.0  # 5 conversions / 5 clicks

    def test_get_conversion_rate_no_clicks(self, tracker, sample_link):
        rate = tracker.get_conversion_rate(sample_link.link_id)
        assert rate == 0.0

    def test_get_top_links_by_revenue(self, tracker, tracked_link):
        top = tracker.get_top_links(metric="revenue", limit=5)
        assert len(top) >= 1
        link, rev = top[0]
        assert rev == pytest.approx(5 * 29.99, 0.01)

    def test_get_top_links_by_commission(self, tracker, tracked_link):
        top = tracker.get_top_links(metric="commission", limit=5)
        assert len(top) >= 1
        link, comm = top[0]
        assert comm == pytest.approx(5 * 2.99, 0.01)


# ===================================================================
# SECTION 2: AffiliateAnalytics (20 tests)
# ===================================================================

class TestAffiliateAnalytics:
    def test_daily_report_structure(self, tracker, analytics, tracked_link):
        report = analytics.daily_report("2026-06-01")
        assert isinstance(report, RevenueReport)
        assert report.period.startswith("daily")
        assert report.total_clicks >= 0
        assert report.total_conversions >= 0

    def test_daily_report_with_data(self, tracker, analytics, tracked_link):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        report = analytics.daily_report(today)
        assert report.total_clicks == 5
        assert report.total_conversions == 5
        assert report.total_revenue_usd == pytest.approx(5 * 29.99, 0.01)

    def test_daily_report_conversion_rate(self, tracker, analytics, tracked_link):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        report = analytics.daily_report(today)
        assert report.conversion_rate == 1.0

    def test_daily_report_avg_order_value(self, tracker, analytics, tracked_link):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        report = analytics.daily_report(today)
        assert report.avg_order_value_usd == pytest.approx(29.99, 0.01)

    def test_weekly_report(self, tracker, analytics, tracked_link):
        today = datetime.now(timezone.utc)
        iso_year, iso_week, _ = today.isocalendar()
        week_str = f"{iso_year}-W{iso_week:02d}"
        report = analytics.weekly_report(week_str)
        assert report.period.startswith("weekly")
        assert report.total_clicks == 5
        assert report.total_conversions == 5

    def test_monthly_report(self, tracker, analytics, tracked_link):
        today = datetime.now(timezone.utc)
        month_str = today.strftime("%Y-%m")
        report = analytics.monthly_report(month_str)
        assert report.period.startswith("monthly")
        assert report.total_clicks >= 5

    def test_empty_report(self, analytics):
        report = analytics.daily_report("2020-01-01")
        assert report.total_clicks == 0
        assert report.total_conversions == 0
        assert report.total_revenue_usd == 0.0
        assert report.conversion_rate == 0.0

    def test_niche_breakdown(self, tracker, analytics, tracked_link):
        breakdown = analytics.niche_breakdown(days=30)
        assert isinstance(breakdown, dict)
        # niche may be 'unknown' since metadata has no niche
        assert "unknown" in breakdown or len(breakdown) == 0

    def test_niche_breakdown_with_niche(self, tracker, analytics):
        link = tracker.create_link(
            "p1", "shopee", "https://ex.com/p", "aff-1",
            metadata={"niche": "beauty"},
        )
        click = tracker.record_click(link.short_code, "UA", "1.2.3.4", "ref")
        assert click is not None
        tracker.record_conversion(click.click_id, "ORD-1", 50.0, 5.0)
        breakdown = analytics.niche_breakdown(days=30)
        assert breakdown.get("beauty", 0.0) == pytest.approx(50.0, 0.01)

    def test_platform_breakdown(self, tracker, analytics, tracked_link):
        breakdown = analytics.platform_breakdown(days=30)
        assert isinstance(breakdown, dict)
        assert "shopee" in breakdown

    def test_platform_breakdown_multiple(self, tracker, analytics):
        for plat in ["shopee", "tokopedia", "lazada"]:
            link = tracker.create_link(f"p-{plat}", plat, f"https://{plat}.com/p", "aff-1")
            click = tracker.record_click(link.short_code, "UA", "1.2.3.4", "ref")
            assert click is not None
            tracker.record_conversion(click.click_id, f"ORD-{plat}", 25.0, 2.5)
        breakdown = analytics.platform_breakdown(days=30)
        assert len(breakdown) == 3

    def test_forecast_revenue_with_data(self, tracker, analytics, tracked_link):
        forecast = analytics.forecast_revenue(days_ahead=30)
        # At least 1 day of data = some forecast (even if 0 for single day)
        assert forecast >= 0

    def test_forecast_revenue_no_data(self, analytics):
        forecast = analytics.forecast_revenue(days_ahead=30)
        assert forecast == 0.0

    def test_detect_anomalies(self, tracker, analytics, tracked_link):
        anomalies = analytics.detect_anomalies(days=30)
        assert isinstance(anomalies, list)

    def test_detect_anomalies_no_data(self, analytics):
        anomalies = analytics.detect_anomalies(days=30)
        assert anomalies == []

    def test_export_csv(self, tracker, analytics, tracked_link):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        report = analytics.daily_report(today)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            csv_path = f.name
        try:
            analytics.export_csv(report, csv_path)
            assert os.path.getsize(csv_path) > 0
            with open(csv_path) as f:
                content = f.read()
            assert "total_revenue_usd" in content
            assert "total_clicks" in content
        finally:
            os.unlink(csv_path)

    def test_daily_report_top_products(self, tracker, analytics, tracked_link):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        report = analytics.daily_report(today)
        assert len(report.top_products) >= 1

    def test_daily_report_top_platforms(self, tracker, analytics, tracked_link):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        report = analytics.daily_report(today)
        assert len(report.top_platforms) >= 1

    def test_daily_report_daily_breakdown(self, tracker, analytics, tracked_link):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        report = analytics.daily_report(today)
        assert len(report.daily_breakdown) >= 1


# ===================================================================
# SECTION 3: CaptionLinkInjector (15 tests)
# ===================================================================

class TestCaptionLinkInjector:
    def test_inject_auto_appends(self, injector, sample_link):
        caption = "Check out this amazing product!"
        result = injector.inject(caption, sample_link)
        assert sample_link.short_code in result
        assert caption in result
        assert "https://ugc.ai/r/" in result

    def test_inject_start_position(self, injector, sample_link):
        caption = "Amazing product!"
        result = injector.inject(caption, sample_link, position="start")
        assert result.startswith("🛒")

    def test_inject_end_position(self, injector, sample_link):
        caption = "Amazing product!"
        result = injector.inject(caption, sample_link, position="end")
        assert caption in result
        assert result.endswith("...") is False  # not truncated

    def test_inject_before_hashtags(self, injector, sample_link):
        caption = "Great product! #skincare #beauty"
        result = injector.inject(caption, sample_link, position="after_hash")
        assert "#skincare" in result
        assert "#beauty" in result
        # Link should be before hashtags
        link_pos = result.index("https://ugc.ai")
        hash_pos = result.index("#skincare")
        assert link_pos < hash_pos

    def test_inject_auto_places_before_hashtags(self, injector, sample_link):
        caption = "Great product! #skincare #beauty"
        result = injector.inject(caption, sample_link, position="auto")
        link_pos = result.index("https://ugc.ai")
        hash_pos = result.index("#skincare")
        assert link_pos < hash_pos

    def test_inject_before_cta(self, injector, sample_link):
        caption = "I love this product. Shop now for discounts!"
        result = injector.inject(caption, sample_link, position="before_cta")
        assert "https://ugc.ai" in result
        assert "Shop now" in result

    def test_inject_truncates_long_caption(self, injector, sample_link):
        caption = "A" * 2190
        result = injector.inject(caption, sample_link, position="end")
        assert len(result) <= 2203  # 2200 + "..."

    def test_inject_batch(self, injector, sample_link, tracker):
        link2 = tracker.create_link("p2", "tokopedia", "https://tokopedia.com/p", "aff-2")
        captions = ["First caption!", "Second caption!"]
        links = [sample_link, link2]
        results = injector.inject_batch(captions, links)
        assert len(results) == 2
        assert sample_link.short_code in results[0]
        assert link2.short_code in results[1]

    def test_suggest_placement_end(self, injector, sample_link):
        caption = "Plain caption without hashtags or URLs"
        pos = injector.suggest_placement(caption, "shopee")
        assert pos == len(caption)

    def test_suggest_placement_before_hashtags(self, injector, sample_link):
        caption = "Great stuff! #skincare"
        pos = injector.suggest_placement(caption, "shopee")
        assert pos == caption.index("#skincare")

    def test_validate_caption_valid(self, injector):
        valid, reason = injector.validate_caption("Great product!", "shopee")
        assert valid is True
        assert reason == ""

    def test_validate_caption_empty(self, injector):
        valid, reason = injector.validate_caption("", "shopee")
        assert valid is False
        assert "empty" in reason

    def test_validate_caption_placeholder(self, injector):
        valid, reason = injector.validate_caption("Buy now [link]", "shopee")
        assert valid is False
        assert "placeholder" in reason

    def test_validate_caption_script_tag(self, injector):
        valid, reason = injector.validate_caption(
            '<script>alert("xss")</script>', "shopee",
        )
        assert valid is False
        assert "script" in reason

    def test_validate_caption_too_long(self, injector):
        valid, reason = injector.validate_caption("A" * 2500, "shopee")
        assert valid is False
        assert "2200" in reason

    def test_inject_platform_specific_emoji(self, injector):
        # Shopee uses 🛒
        caption = "Check this!"
        result = injector.inject(caption, AffiliateLink(
            link_id="test", product_id="p1", platform="tokopedia",
            base_url="https://tokopedia.com/p", affiliate_id="aff-1",
            short_code="ABC123",
        ))
        assert "🛍️" in result  # Tokopedia emoji

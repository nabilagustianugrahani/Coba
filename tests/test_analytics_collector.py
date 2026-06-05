"""Tests for AnalyticsCollector."""
import os
import sys
import tempfile
import pytest

# Ensure repo root on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from ugc_ai_overpower.core.analytics_collector import AnalyticsCollector


@pytest.fixture
def collector(tmp_path):
    """Create a collector backed by a temp DB so we don't pollute real data."""
    db = str(tmp_path / "test_content_bank.db")
    from ugc_ai_overpower.core.content_bank_v2 import ContentBankV2
    bank = ContentBankV2(db_path=db)
    pid = bank.add_product("Test Serum", category="skincare")
    cid = bank.add_content(
        hook="Test hook",
        script="Test script",
        platform="tiktok",
        product_id=pid,
        status="posted",
    )
    bank.update_performance(cid, views=1000, likes=80, comments=10, shares=5, clicks=12)
    return AnalyticsCollector(bank=bank)


def test_collect_from_bank_returns_aggregated_rows(collector):
    rows = collector.collect_from_bank()
    assert isinstance(rows, list)
    assert len(rows) >= 1
    row = rows[0]
    assert row["product_name"] == "Test Serum"
    assert row["platform"] == "tiktok"
    assert row["views"] == 1000
    assert row["likes"] == 80
    assert row["comments"] == 10
    assert row["shares"] == 5
    assert row["clicks"] == 12
    assert row["content_count"] == 1


def test_collect_per_content_returns_per_row(collector):
    rows = collector.collect_per_content()
    assert len(rows) >= 1
    assert rows[0]["views"] == 1000
    assert rows[0]["product_name"] == "Test Serum"


def test_daily_aggregate_sums_metrics(collector):
    agg = collector.daily_aggregate()
    assert agg["content_count"] == 1
    assert agg["views"] == 1000
    assert agg["likes"] == 80
    assert agg["comments"] == 10
    assert agg["shares"] == 5
    assert agg["clicks"] == 12
    assert "engagement_rate" in agg
    assert "collected_at" in agg


def test_push_to_notion_handles_missing_config(collector, monkeypatch):
    """When NOTION_TOKEN is missing, push_to_notion should return an error dict
    rather than raising."""
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    result = collector.push_to_notion()
    assert result["status"] == "error"
    assert "not configured" in result["message"].lower()


def test_daily_aggregate_handles_empty_bank(tmp_path):
    from ugc_ai_overpower.core.content_bank_v2 import ContentBankV2
    bank = ContentBankV2(db_path=str(tmp_path / "empty.db"))
    c = AnalyticsCollector(bank=bank)
    agg = c.daily_aggregate()
    assert agg["views"] == 0
    assert agg["content_count"] == 0

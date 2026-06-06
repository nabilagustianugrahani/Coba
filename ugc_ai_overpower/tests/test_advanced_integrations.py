"""Tests for relationship_graph, trend_detector, umami_dispatch, social_scheduler."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture
def tmpdir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture(autouse=True)
def isolate(tmpdir, monkeypatch):
    monkeypatch.setenv("UGC_GRAPH_DB", str(tmpdir / "graph.db"))
    monkeypatch.setenv("UGC_TREND_DB", str(tmpdir / "trends.db"))
    monkeypatch.setenv("UGC_UMAMI_DB", str(tmpdir / "umami.db"))
    monkeypatch.setenv("UGC_SCHEDULER_DB", str(tmpdir / "sched.db"))
    monkeypatch.setenv("UMAMI_BASE_URL", "http://localhost:3000")
    monkeypatch.setenv("UMAMI_WEBSITE_ID", "test-website-id")
    yield


def test_relationship_graph_imports():
    from ugc_ai_overpower.integrations.relationship_graph import (
        Node, Edge, NodeType, EdgeType, RelationshipGraph,
    )
    assert RelationshipGraph is not None
    assert NodeType.CREATOR.value == "creator"
    assert EdgeType.POSTED.value == "posted"


def test_relationship_graph_add_node(tmpdir):
    from ugc_ai_overpower.integrations.relationship_graph import RelationshipGraph
    g = RelationshipGraph()
    n = g.add_node("creator", "Sari", {"age": 27, "location": "Jakarta"})
    assert n.node_type == "creator"
    assert n.name == "Sari"
    assert n.properties["age"] == 27


def test_relationship_graph_add_edge(tmpdir):
    from ugc_ai_overpower.integrations.relationship_graph import RelationshipGraph
    g = RelationshipGraph()
    a = g.add_node("creator", "Sari")
    b = g.add_node("content", "Lipstick Review")
    e = g.add_edge(a.node_id, b.node_id, "created", {"ts": "2026-01-01"})
    assert e.from_node == a.node_id
    assert e.to_node == b.node_id
    assert e.edge_type == "created"
    assert e.weight == 1.0


def test_relationship_graph_get_node(tmpdir):
    from ugc_ai_overpower.integrations.relationship_graph import RelationshipGraph
    g = RelationshipGraph()
    n = g.add_node("creator", "Rizky", {"age": 30})
    loaded = g.get_node(n.node_id)
    assert loaded is not None
    assert loaded.name == "Rizky"


def test_relationship_graph_find_nodes_by_type(tmpdir):
    from ugc_ai_overpower.integrations.relationship_graph import RelationshipGraph
    g = RelationshipGraph()
    g.add_node("creator", "A")
    g.add_node("creator", "B")
    g.add_node("content", "X")
    creators = g.find_nodes(node_type="creator")
    assert len(creators) == 2
    contents = g.find_nodes(node_type="content")
    assert len(contents) == 1


def test_relationship_graph_find_nodes_by_name(tmpdir):
    from ugc_ai_overpower.integrations.relationship_graph import RelationshipGraph
    g = RelationshipGraph()
    g.add_node("creator", "Sari Beauty")
    g.add_node("creator", "Rizky Tech")
    sari = g.find_nodes(name_pattern="Sari")
    assert len(sari) == 1
    assert sari[0].name == "Sari Beauty"


def test_relationship_graph_find_related(tmpdir):
    from ugc_ai_overpower.integrations.relationship_graph import RelationshipGraph
    g = RelationshipGraph()
    creator = g.add_node("creator", "Sari")
    c1 = g.add_node("content", "Post 1")
    c2 = g.add_node("content", "Post 2")
    niche = g.add_node("niche", "Beauty")
    g.add_edge(creator.node_id, c1.node_id, "created")
    g.add_edge(creator.node_id, c2.node_id, "created")
    g.add_edge(creator.node_id, niche.node_id, "targets")
    related = g.find_related(creator.node_id)
    assert len(related) == 3


def test_relationship_graph_find_related_outgoing(tmpdir):
    from ugc_ai_overpower.integrations.relationship_graph import RelationshipGraph
    g = RelationshipGraph()
    a = g.add_node("creator", "A")
    b = g.add_node("creator", "B")
    content = g.add_node("content", "X")
    g.add_edge(a.node_id, b.node_id, "engaged_with")
    g.add_edge(a.node_id, content.node_id, "created")
    out = g.find_related(a.node_id, direction="out")
    assert len(out) == 2
    incoming = g.find_related(b.node_id, direction="in")
    assert len(incoming) == 1


def test_relationship_graph_find_related_by_type(tmpdir):
    from ugc_ai_overpower.integrations.relationship_graph import RelationshipGraph
    g = RelationshipGraph()
    a = g.add_node("creator", "A")
    b = g.add_node("content", "B")
    c = g.add_node("niche", "C")
    g.add_edge(a.node_id, b.node_id, "created")
    g.add_edge(a.node_id, c.node_id, "targets")
    out = g.find_related(a.node_id, edge_types=["created"])
    assert len(out) == 1
    assert out[0][1].node_id == b.node_id


def test_relationship_graph_search(tmpdir):
    from ugc_ai_overpower.integrations.relationship_graph import RelationshipGraph
    g = RelationshipGraph()
    g.add_node("creator", "Sari Beauty", {"specialty": "skincare"})
    g.add_node("creator", "Rizky Tech", {"specialty": "gadgets"})
    results = g.search("skincare")
    assert len(results) >= 1
    assert any("Sari" in n.name for n in results)


def test_relationship_graph_subgraph(tmpdir):
    from ugc_ai_overpower.integrations.relationship_graph import RelationshipGraph
    g = RelationshipGraph()
    a = g.add_node("creator", "A")
    b = g.add_node("content", "B")
    c = g.add_node("content", "C")
    g.add_edge(a.node_id, b.node_id, "created")
    g.add_edge(a.node_id, c.node_id, "created")
    g.add_edge(b.node_id, c.node_id, "mentioned")
    sg = g.subgraph(a.node_id, depth=2)
    assert "nodes" in sg
    assert "edges" in sg
    assert len(sg["nodes"]) >= 2


def test_relationship_graph_stats(tmpdir):
    from ugc_ai_overpower.integrations.relationship_graph import RelationshipGraph
    g = RelationshipGraph()
    a = g.add_node("creator", "A")
    b = g.add_node("content", "B")
    g.add_edge(a.node_id, b.node_id, "created")
    s = g.stats()
    assert s["total_nodes"] == 2
    assert s["total_edges"] == 1
    assert s["nodes_by_type"]["creator"] == 1


def test_relationship_graph_clear(tmpdir):
    from ugc_ai_overpower.integrations.relationship_graph import RelationshipGraph
    g = RelationshipGraph()
    g.add_node("creator", "A")
    g.add_node("content", "B")
    g.clear()
    s = g.stats()
    assert s["total_nodes"] == 0


def test_node_to_dict():
    from ugc_ai_overpower.integrations.relationship_graph import Node
    n = Node(node_id="x", node_type="creator", name="X")
    d = n.to_dict()
    assert d["node_id"] == "x"


def test_edge_to_dict():
    from ugc_ai_overpower.integrations.relationship_graph import Edge
    e = Edge(edge_id="x", from_node="a", to_node="b", edge_type="created")
    d = e.to_dict()
    assert d["edge_id"] == "x"


def test_trend_detector_imports():
    from ugc_ai_overpower.core.trend_detector import (
        TrendSignal, AuthorityAccount, NicheAuthorityConfig,
        TrendDetector, TrendCategory, SourcePlatform,
        NICHE_AUTHORITIES,
    )
    assert TrendDetector is not None
    assert "beauty" in NICHE_AUTHORITIES
    assert "tech" in NICHE_AUTHORITIES


def test_trend_detector_record_signal():
    from ugc_ai_overpower.core.trend_detector import TrendDetector
    td = TrendDetector()
    sig = td.record_signal(
        url="https://example.com/post/1",
        title="Viral lipstick",
        category="product",
        platform="tiktok",
        niche="beauty",
        shared_by="mikaylanogueira",
        engagement_count=10000,
    )
    assert sig.signal_id != ""
    assert sig.niche == "beauty"
    assert "mikaylanogueira" in sig.shared_by


def test_trend_detector_score_increases_with_sharers():
    from ugc_ai_overpower.core.trend_detector import TrendDetector
    td = TrendDetector()
    s1 = td.record_signal(
        url="https://example.com/p/1", title="X", category="product",
        platform="tiktok", niche="beauty", shared_by="user1", engagement_count=1000,
    )
    s2 = td.record_signal(
        url="https://example.com/p/1", title="X", category="product",
        platform="tiktok", niche="beauty", shared_by="user2", engagement_count=5000,
    )
    s3 = td.record_signal(
        url="https://example.com/p/1", title="X", category="product",
        platform="tiktok", niche="beauty", shared_by="user3", engagement_count=2000,
    )
    assert s3.score > s1.score


def test_trend_detector_get_trending():
    from ugc_ai_overpower.core.trend_detector import TrendDetector
    td = TrendDetector()
    for i in range(5):
        td.record_signal(
            url=f"https://example.com/p/{i}", title=f"Post {i}",
            category="product", platform="tiktok", niche="beauty",
            shared_by=f"user{i}", engagement_count=1000 * (i + 1),
        )
    trending = td.get_trending(niche="beauty", limit=10)
    assert len(trending) >= 3


def test_trend_detector_get_trending_by_category():
    from ugc_ai_overpower.core.trend_detector import TrendDetector
    td = TrendDetector()
    td.record_signal(
        url="https://example.com/p/1", title="X", category="product",
        platform="tiktok", niche="beauty", shared_by="u1", engagement_count=1000,
    )
    td.record_signal(
        url="https://example.com/p/2", title="Y", category="meme",
        platform="tiktok", niche="beauty", shared_by="u2", engagement_count=500,
    )
    products = td.get_trending(niche="beauty", category="product")
    assert all(s.category == "product" for s in products)


def test_trend_detector_decay():
    from ugc_ai_overpower.core.trend_detector import TrendDetector
    td = TrendDetector()
    td.record_signal(
        url="https://example.com/p/1", title="X", category="product",
        platform="tiktok", niche="beauty", shared_by="u1", engagement_count=100,
    )
    n = td.decay_scores()
    assert n == 1


def test_trend_detector_stats():
    from ugc_ai_overpower.core.trend_detector import TrendDetector
    td = TrendDetector()
    td.record_signal(
        url="https://example.com/p/1", title="X", category="product",
        platform="tiktok", niche="beauty", shared_by="u1", engagement_count=100,
    )
    s = td.stats()
    assert s["total_signals"] == 1
    assert "beauty" in s["by_niche"]


def test_trend_detector_add_niche_config():
    from ugc_ai_overpower.core.trend_detector import (
        TrendDetector, NicheAuthorityConfig, AuthorityAccount,
    )
    td = TrendDetector()
    cfg = NicheAuthorityConfig(
        niche="gaming",
        accounts=[AuthorityAccount("twitter", "ign", "gaming", 1.0, 10000000)],
    )
    td.add_niche_config(cfg)
    assert "gaming" in td.configs


def test_trend_detector_compute_score_decay():
    from ugc_ai_overpower.core.trend_detector import TrendDetector, NicheAuthorityConfig
    td = TrendDetector()
    cfg = NicheAuthorityConfig(niche="beauty", decay_rate=0.5)
    td.add_niche_config(cfg)
    now = "2026-06-06T12:00:00+00:00"
    future = "2026-06-06T13:00:00+00:00"
    fresh = td._compute_score(["a", "b"], now, now, 100, cfg)
    aged = td._compute_score(["a", "b"], future, now, 100, cfg)
    assert fresh > aged


def test_authority_account_defaults():
    from ugc_ai_overpower.core.trend_detector import AuthorityAccount
    a = AuthorityAccount(platform="twitter", handle="x", niche="beauty")
    assert a.weight == 1.0
    assert a.is_active is True


def test_umami_dispatch_imports():
    from ugc_ai_overpower.integrations.umami_dispatch import (
        TrackingEvent, UmamiDispatcher, DEFAULT_BASE_URL,
    )
    assert UmamiDispatcher is not None


def test_umami_is_configured():
    from ugc_ai_overpower.integrations.umami_dispatch import UmamiDispatcher
    ud = UmamiDispatcher()
    assert ud.is_configured() is True


def test_umami_track_event():
    from ugc_ai_overpower.integrations.umami_dispatch import UmamiDispatcher
    ud = UmamiDispatcher()
    ev = ud.track(
        url="https://instagram.com/p/abc",
        event_name="ugc_post_published",
        session_id="s1",
        user_id="sari_beauty",
    )
    assert ev.event_id != ""
    assert ev.event_name == "ugc_post_published"


def test_umami_track_ugc_post():
    from ugc_ai_overpower.integrations.umami_dispatch import UmamiDispatcher
    ud = UmamiDispatcher()
    ev = ud.track_ugc_post(
        post_url="https://tiktok.com/@sari/video/123",
        platform="tiktok",
        content_id="content_42",
        character_id="sari_beauty",
        niche="beauty",
    )
    assert ev.metadata["platform"] == "tiktok"
    assert ev.metadata["character_id"] == "sari_beauty"


def test_umami_track_engagement():
    from ugc_ai_overpower.integrations.umami_dispatch import UmamiDispatcher
    ud = UmamiDispatcher()
    ev = ud.track_engagement(
        post_url="https://instagram.com/p/abc",
        platform="instagram",
        views=1000, likes=100, shares=10, comments=5,
    )
    assert ev.metadata["views"] == 1000
    assert ev.metadata["likes"] == 100


def test_umami_track_affiliate_click():
    from ugc_ai_overpower.integrations.umami_dispatch import UmamiDispatcher
    ud = UmamiDispatcher()
    ev = ud.track_affiliate_click(
        affiliate_url="https://shope.ee/abc",
        platform="shopee",
        product_id="999",
        character_id="sari_beauty",
    )
    assert ev.event_name == "affiliate_click"
    assert ev.metadata["product_id"] == "999"


def test_umami_stats():
    from ugc_ai_overpower.integrations.umami_dispatch import UmamiDispatcher
    ud = UmamiDispatcher()
    ud.track(url="https://x.com/p/1", event_name="test")
    s = ud.stats()
    assert s["total_events"] == 1
    assert s["configured"] is True


def test_umami_daily_rollup():
    from ugc_ai_overpower.integrations.umami_dispatch import UmamiDispatcher
    from datetime import datetime, timezone
    ud = UmamiDispatcher()
    today = datetime.now(timezone.utc).date().isoformat()
    ud.track(url="https://instagram.com/p/abc", event_name="view")
    ud.track(url="https://instagram.com/p/abc", event_name="like")
    rollup = ud.daily_rollup(today)
    assert rollup["total_events"] >= 2
    assert rollup["unique_urls"] >= 1


def test_umami_payload_structure():
    from ugc_ai_overpower.integrations.umami_dispatch import TrackingEvent
    ev = TrackingEvent(
        event_id="x", website_id="site1", url="https://x.com/p/1",
        event_name="test", metadata={"a": 1},
    )
    p = ev.to_payload()
    assert p["website"] == "site1"
    assert p["name"] == "test"
    assert p["data"]["a"] == 1


def test_social_scheduler_imports():
    from ugc_ai_overpower.core.social_scheduler import (
        ScheduledPost, SocialScheduler, PostStatus, ScheduleStrategy,
        PLATFORM_OPTIMAL_TIMES, DEFAULT_DB_PATH,
    )
    assert SocialScheduler is not None
    assert PostStatus.PENDING.value == "pending"
    assert "tiktok" in PLATFORM_OPTIMAL_TIMES


def test_social_scheduler_schedule():
    from ugc_ai_overpower.core.social_scheduler import SocialScheduler
    s = SocialScheduler()
    p = s.schedule(
        platform="tiktok", username="sari",
        content="Hello world", niche="beauty", character_id="sari_beauty",
    )
    assert p.post_id != ""
    assert p.platform == "tiktok"
    assert p.status in ("pending", "scheduled")


def test_social_scheduler_schedule_specific_time():
    from ugc_ai_overpower.core.social_scheduler import SocialScheduler
    from datetime import datetime, timezone, timedelta
    s = SocialScheduler()
    future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    p = s.schedule(
        platform="instagram", username="sari", content="test",
        scheduled_at=future, character_id="sari_beauty",
    )
    assert p.status == "scheduled"
    assert p.scheduled_at == future


def test_social_scheduler_optimal_strategy():
    from ugc_ai_overpower.core.social_scheduler import SocialScheduler, ScheduleStrategy
    s = SocialScheduler()
    p = s.schedule(
        platform="tiktok", username="sari", content="test",
        strategy=ScheduleStrategy.OPTIMAL.value,
    )
    assert p.scheduled_at != ""


def test_social_scheduler_due_posts():
    from ugc_ai_overpower.core.social_scheduler import SocialScheduler
    from datetime import datetime, timezone, timedelta
    s = SocialScheduler()
    past = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    s.schedule(
        platform="tiktok", username="sari", content="past1",
        scheduled_at=past,
    )
    future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    s.schedule(
        platform="instagram", username="sari", content="future1",
        scheduled_at=future,
    )
    due = s.due_posts()
    assert all(p.content == "past1" for p in due)


def test_social_scheduler_lifecycle():
    from ugc_ai_overpower.core.social_scheduler import SocialScheduler
    s = SocialScheduler()
    p = s.schedule(platform="tiktok", username="sari", content="test")
    s.mark_publishing(p.post_id)
    loaded = s.get(p.post_id)
    assert loaded.status == "publishing"
    s.mark_published(p.post_id)
    loaded = s.get(p.post_id)
    assert loaded.status == "published"
    assert loaded.published_at != ""


def test_social_scheduler_mark_failed():
    from ugc_ai_overpower.core.social_scheduler import SocialScheduler
    s = SocialScheduler()
    p = s.schedule(platform="tiktok", username="sari", content="test")
    s.mark_failed(p.post_id, "test error")
    loaded = s.get(p.post_id)
    assert loaded.error == "test error"
    assert loaded.retry_count == 1


def test_social_scheduler_cancel():
    from ugc_ai_overpower.core.social_scheduler import SocialScheduler
    s = SocialScheduler()
    p = s.schedule(platform="tiktok", username="sari", content="test")
    assert s.cancel(p.post_id) is True
    loaded = s.get(p.post_id)
    assert loaded.status == "cancelled"
    assert s.cancel(p.post_id) is False


def test_social_scheduler_list_by_character():
    from ugc_ai_overpower.core.social_scheduler import SocialScheduler
    s = SocialScheduler()
    s.schedule(platform="tiktok", username="u1", content="a", character_id="char1")
    s.schedule(platform="tiktok", username="u2", content="b", character_id="char1")
    s.schedule(platform="tiktok", username="u3", content="c", character_id="char2")
    char1_posts = s.list_by_character("char1")
    assert len(char1_posts) == 2


def test_social_scheduler_list_by_campaign():
    from ugc_ai_overpower.core.social_scheduler import SocialScheduler
    s = SocialScheduler()
    s.schedule(platform="tiktok", username="u", content="a", campaign_id="c1")
    s.schedule(platform="instagram", username="u", content="b", campaign_id="c1")
    posts = s.list_by_campaign("c1")
    assert len(posts) == 2


def test_social_scheduler_list_by_status():
    from ugc_ai_overpower.core.social_scheduler import SocialScheduler
    s = SocialScheduler()
    p1 = s.schedule(platform="tiktok", username="u", content="a")
    s.schedule(platform="instagram", username="u", content="b")
    s.mark_published(p1.post_id)
    published = s.list_by_status("published")
    assert len(published) == 1


def test_social_scheduler_stats():
    from ugc_ai_overpower.core.social_scheduler import SocialScheduler
    s = SocialScheduler()
    s.schedule(platform="tiktok", username="u", content="a")
    s.schedule(platform="instagram", username="u", content="b")
    stats = s.stats()
    assert stats["total"] == 2
    assert "tiktok" in stats["by_platform"]


def test_social_scheduler_platform_optimal_times():
    from ugc_ai_overpower.core.social_scheduler import PLATFORM_OPTIMAL_TIMES
    assert len(PLATFORM_OPTIMAL_TIMES["tiktok"]) >= 1
    assert all(isinstance(slot, tuple) for slot in PLATFORM_OPTIMAL_TIMES["tiktok"])


def test_social_scheduler_next_optimal_slot():
    from ugc_ai_overpower.core.social_scheduler import SocialScheduler
    from datetime import datetime, timezone
    s = SocialScheduler()
    now = datetime.now(timezone.utc)
    slot = s._next_optimal_slot("tiktok", now)
    assert slot > now.isoformat()


def test_scheduled_post_to_dict():
    from ugc_ai_overpower.core.social_scheduler import ScheduledPost
    p = ScheduledPost(
        post_id="x", platform="tiktok", username="u", content="test",
    )
    d = p.to_dict()
    assert d["post_id"] == "x"
    assert d["status"] == "pending"

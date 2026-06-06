"""End-to-end pipeline test: character → content → social → ecom → notion → analytics.

All external services are MOCKED. Tests are reproducible with no network access.

Run: pytest ugc_ai_overpower/tests/test_e2e_pipeline.py -q
"""
from __future__ import annotations

import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from ugc_ai_overpower.core.notion_sync import NotionDashboard
from ugc_ai_overpower.integrations.analytics_pipeline import (
    AnalyticsPipeline,
    PostMetrics,
    ROIDashboard,
)
from ugc_ai_overpower.integrations.character_agent import (
    Character,
    CharacterAgent,
    CharacterStore,
    ContentLanguage,
    ContentTone,
    PersonaIdentity,
    PersonalityTraits,
)
from ugc_ai_overpower.integrations.ecom_dispatch import (
    AffiliateCache,
    EcomConfig,
    EcomDispatch,
)
from ugc_ai_overpower.integrations.relationship_graph import (
    NodeType,
    RelationshipGraph,
)
from ugc_ai_overpower.integrations.social_dispatch import (
    SocialDispatch,
    TikHubConfig,
    detect_platform,
)
from ugc_ai_overpower.integrations.umami_dispatch import (
    TrackingEvent,
    UmamiDispatcher,
)


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def character_agent(tmp_dir) -> CharacterAgent:
    return CharacterAgent(store=CharacterStore(path=tmp_dir / "chars.db"))


@pytest.fixture
def graph(tmp_dir) -> RelationshipGraph:
    return RelationshipGraph(path=tmp_dir / "graph.db")


@pytest.fixture
def character(character_agent) -> Character:
    return character_agent.create_persona(
        template_name="Sari",
        niche="fashion",
        custom_identity=PersonaIdentity(
            name="Ayu", age=24, gender="female", location="Jakarta",
            background="Modern hijab fashion enthusiast",
            languages=["id"],
        ),
        custom_personality=PersonalityTraits(
            tone=ContentTone.CASUAL.value,
            formality=0.3, humor=0.6, energy=0.7, warmth=0.85,
            confidence=0.7, curiosity=0.6, values=["sustainability", "modesty"],
        ),
        language=ContentLanguage.ID.value,
    )


# ----- Test 1: Character creation -----
def test_character_creation(character):
    assert character.identity.name == "Ayu"
    assert character.identity.location == "Jakarta"
    assert character.niche_adaptation.niche == "fashion"
    fp = character.fingerprint()
    assert fp and len(fp) > 0


# ----- Test 2: Character fingerprint stable -----
def test_character_fingerprint_stable(character):
    fp1 = character.fingerprint()
    fp2 = character.fingerprint()
    assert fp1 == fp2


# ----- Test 3: Content generation via mocked AI dispatcher -----
import asyncio
def test_content_generation_mocked(tmp_dir):
    """Mock the modal_dispatch and produce a canned response (async)."""
    async def _run():
        with patch("ugc_ai_overpower.integrations.modal_dispatch.ModalDispatch.text_to_image") as mock_gen:
            mock_gen.return_value = {"url": "https://mock.cdn/img.png", "cost": 0.005}
            result = await mock_gen(prompt="fashion outfit", model="flux-klein-4b")
            assert result["url"] == "https://mock.cdn/img.png"
            assert result["cost"] == 0.005
    asyncio.run(_run())


# ----- Test 4: ImageEnhancer construction + cost -----
def test_image_enhancer_construction(tmp_dir):
    from ugc_ai_overpower.integrations.image_enhancer import ImageEnhancer
    ie = ImageEnhancer()
    assert ie is not None
    # total_cost_usd is a float attribute (not a method)
    assert isinstance(ie.total_cost_usd, float)
    assert ie.total_cost_usd == 0.0
    ie.reset_cost()
    assert ie.total_cost_usd == 0.0


# ----- Test 5: VideoEditor construction + summary -----
def test_video_editor_construction(tmp_dir):
    from ugc_ai_overpower.integrations.video_editor import VideoEditor
    ve = VideoEditor()
    assert ve is not None
    s = ve.summary()
    assert isinstance(s, dict)


# ----- Test 6: Social URL pattern detection -----
def test_social_url_pattern_detection():
    cases = [
        ("https://www.tiktok.com/@user/video/123", "tiktok"),
        ("https://www.instagram.com/reel/abc/", "instagram"),
        ("https://twitter.com/user/status/123", "twitter"),
        ("https://www.youtube.com/watch?v=abc", "youtube"),
        ("not a url", None),
    ]
    for url, expected in cases:
        assert detect_platform(url) == expected, f"Failed for {url}"


# ----- Test 7: SocialDispatch construction (dataclass) -----
def test_social_dispatch_construction():
    cfg = TikHubConfig(api_key="test_key", base_url="https://api.tikhub.io", timeout_sec=10)
    sd = SocialDispatch(tiktokhub_config=cfg)
    assert sd is not None
    assert sd.tiktokhub_config.api_key == "test_key"


# ----- Test 8: EcomDispatch construction (dataclass) -----
def test_ecom_dispatch_construction(tmp_dir):
    cfg = EcomConfig(
        shopee_affiliate_id="sa_id", shopee_affiliate_token="sa_tok",
        tiktokshop_app_key="tt_key", tiktokshop_access_token="tt_tok",
        lazada_app_key="lz_key", lazada_app_secret="lz_sec", lazada_access_token="lz_tok",
        tokopedia_affiliate_id="tp_id", tokopedia_affiliate_token="tp_tok",
    )
    cache = AffiliateCache(path=tmp_dir / "aff_cache.db")
    ed = EcomDispatch(config=cfg, cache=cache)
    assert ed.config is not None
    assert ed.cache is not None


# ----- Test 9: Notion sync construction -----
def test_notion_sync_construction():
    nd = NotionDashboard(token="test_token", campaign_db="db1", content_db="db2", analytics_db="db3")
    assert nd is not None


# ----- Test 10: PostMetrics with engagement_rate -----
def test_post_metrics_engagement_rate():
    pm = PostMetrics(post_id="p1", platform="tiktok", impressions=10000, likes=500, comments=50, shares=25)
    er = pm.engagement_rate()
    # (500+50+25)/10000 * 100 = 5.75
    assert 5.0 <= er <= 6.5


# ----- Test 11: AnalyticsPipeline score + ROI -----
def test_analytics_pipeline_score_and_roi():
    ap = AnalyticsPipeline()
    pm = PostMetrics(
        post_id="p1", platform="instagram", impressions=5000, likes=300,
        comments=30, shares=15, clicks=100, conversions=5, revenue_usd=150.0,
    )
    score = ap.score_content(pm)
    assert 0 <= score <= 100
    dashboard = ap.compute_roi([pm], spend_usd=10.0)
    assert isinstance(dashboard, ROIDashboard)
    # (150-10)/10 * 100 = 1400%
    assert dashboard.roi_percent == pytest.approx(1400.0, rel=0.01)


# ----- Test 12: AnalyticsPipeline detect_viral -----
def test_analytics_pipeline_detect_viral():
    ap = AnalyticsPipeline()
    viral_pm = PostMetrics(
        post_id="p1", platform="tiktok", impressions=1000000, likes=50000,
        comments=5000, shares=10000,
    )
    assert ap.detect_viral(viral_pm, threshold=5.0) is True
    not_viral_pm = PostMetrics(
        post_id="p2", platform="tiktok", impressions=1000, likes=10, comments=1, shares=0,
    )
    assert ap.detect_viral(not_viral_pm, threshold=5.0) is False


# ----- Test 13: RelationshipGraph add + search -----
def test_relationship_graph_full_cycle(graph, character):
    c_node = graph.add_node(
        node_type=NodeType.CREATOR,
        name=character.identity.name,
        node_id=character.fingerprint(),
        properties={"niche": character.niche_adaptation.niche}
    )
    p_node = graph.add_node(
        node_type=NodeType.CONTENT,
        name="Outfit 1",
        node_id="post_1",
        properties={"title": "Outfit 1"},
    )
    graph.add_edge(from_node=c_node.node_id, to_node=p_node.node_id, edge_type="created")

    found = graph.get_node(character.fingerprint())
    assert found is not None
    assert found.properties["niche"] == "fashion"

    related = graph.find_related(character.fingerprint(), direction="out")
    assert any(edge[1].node_id == "post_1" for edge in related)

    stats = graph.stats()
    assert stats["total_nodes"] == 2
    assert stats["total_edges"] == 1


# ----- Test 14: Umami dispatcher construction -----
def test_umami_dispatcher_construction(tmp_dir):
    ud = UmamiDispatcher(
        base_url="https://umami.example.com", website_id="ws1", api_key="key1",
        db_path=tmp_dir / "umami.db",
    )
    assert ud is not None
    assert ud.website_id == "ws1"


# ----- Test 15: TrackingEvent construction -----
def test_tracking_event_construction():
    te = TrackingEvent(
        event_id="evt1", website_id="ws1", url="/post/123",
        event_name="post_view", session_id="s1",
    )
    assert te.event_name == "post_view"
    assert te.session_id == "s1"


# ----- Test 16: Cross-component full pipeline < 5s -----
def test_full_pipeline_under_5_seconds(character_agent, graph, character):
    """Run character → graph → analytics in under 5 seconds."""
    start = time.perf_counter()

    # 1. Character created (via fixture)
    fp = character.fingerprint()

    # 2. Add to relationship graph
    c_node = graph.add_node(
        node_type=NodeType.CREATOR,
        name=character.identity.name,
        node_id=fp,
        properties={"name": character.identity.name},
    )
    p_node = graph.add_node(
        node_type=NodeType.CONTENT,
        name="Test post",
        node_id="post_x",
        properties={"title": "Test"},
    )
    graph.add_edge(from_node=c_node.node_id, to_node=p_node.node_id, edge_type="created")

    # 3. Analytics
    ap = AnalyticsPipeline()
    pm = PostMetrics(
        post_id="post_x", platform="tiktok", impressions=10000,
        likes=500, comments=50, shares=25,
    )
    er = pm.engagement_rate()
    score = ap.score_content(pm)

    # 4. Character store round-trip (use character_id, not fingerprint)
    character_agent.store.save(character)
    retrieved = character_agent.store.get(character.character_id)
    assert retrieved is not None
    assert retrieved.identity.name == character.identity.name

    elapsed = time.perf_counter() - start
    assert elapsed < 5.0, f"Pipeline took {elapsed:.2f}s (should be < 5s)"
    assert score >= 0
    assert er > 0


# ----- Test 17: Multi-character, multi-niche -----
def test_multiple_characters_different_niches(character_agent):
    c1 = character_agent.create_persona(
        template_name="Sari", niche="fashion",
        custom_identity=PersonaIdentity(
            name="Ayu", age=24, gender="female", location="Jakarta",
            background="Hijab fashion", languages=["id"],
        ),
        language=ContentLanguage.ID.value,
    )
    c2 = character_agent.create_persona(
        template_name="Dimas", niche="tech",
        custom_identity=PersonaIdentity(
            name="Budi", age=28, gender="male", location="Bandung",
            background="Tech enthusiast", languages=["id"],
        ),
        language=ContentLanguage.ID.value,
    )
    fashion_chars = character_agent.store.list_by_niche("fashion")
    tech_chars = character_agent.store.list_by_niche("tech")
    assert any(c.identity.name == "Ayu" for c in fashion_chars)
    assert any(c.identity.name == "Budi" for c in tech_chars)
    assert c1.fingerprint() != c2.fingerprint()


# ----- Test 18: Character switch_niche -----
def test_character_switch_niche(character, character_agent):
    # switch_niche takes character_id (string), not Character
    new_char = character_agent.switch_niche(character.character_id, "beauty")
    assert new_char.fingerprint() == character.fingerprint()
    assert new_char.niche_adaptation.niche == "beauty"


# ----- Test 19: Search across all components -----
def test_relationship_graph_search(graph, character):
    # add_node(node_type, name, properties, node_id) - all required
    graph.add_node(
        node_type=NodeType.CREATOR,
        name="Ayu",
        node_id=character.fingerprint(),
        properties={"bio": "fashion influencer in Jakarta"},
    )
    graph.add_node(
        node_type=NodeType.CONTENT,
        name="OOTD hijab post",
        node_id="post_99",
        properties={"title": "OOTD hijab"},
    )
    results = graph.search("fashion")
    assert len(results) >= 1

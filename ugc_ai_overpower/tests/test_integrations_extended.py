"""Tests for session_manager, social_dispatch, ecom_dispatch, character_agent."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture
def tmpdir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture(autouse=True)
def isolate_sessions(tmpdir, monkeypatch):
    monkeypatch.setenv("UGC_SESSION_DIR", str(tmpdir / "sessions"))
    monkeypatch.setenv("UGC_SESSION_BACKEND", "sqlite")
    monkeypatch.setenv("UGC_CHARACTER_DB", str(tmpdir / "characters.db"))
    yield


def test_session_module_imports():
    from ugc_ai_overpower.integrations.session_manager import (
        Session, SessionBackend, SessionManager, SessionStatus, SessionStore,
    )
    assert Session is not None
    assert SessionManager is not None


def test_session_dataclass_defaults():
    from ugc_ai_overpower.integrations.session_manager import Session
    s = Session(platform="tiktok", username="test_user")
    assert s.platform == "tiktok"
    assert s.username == "test_user"
    assert s.session_id != ""
    assert s.created_at != ""
    assert s.status == "active"


def test_session_dataclass_custom_id():
    from ugc_ai_overpower.integrations.session_manager import Session
    s = Session(platform="instagram", username="alice", session_id="custom_id_123")
    assert s.session_id == "custom_id_123"


def test_session_touch_updates_last_used():
    from ugc_ai_overpower.integrations.session_manager import Session
    s = Session(platform="tiktok", username="bob")
    original = s.last_used
    s.touch()
    assert s.last_used != original


def test_session_is_expired_no_expiry():
    from ugc_ai_overpower.integrations.session_manager import Session
    s = Session(platform="tiktok", username="x")
    assert s.is_expired() is False


def test_session_is_expired_future():
    from ugc_ai_overpower.integrations.session_manager import Session
    from datetime import datetime, timezone, timedelta
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    s = Session(platform="tiktok", username="x", expires_at=future)
    assert s.is_expired() is False


def test_session_is_expired_past():
    from ugc_ai_overpower.integrations.session_manager import Session
    from datetime import datetime, timezone, timedelta
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    s = Session(platform="tiktok", username="x", expires_at=past)
    assert s.is_expired() is True


def test_session_to_from_dict():
    from ugc_ai_overpower.integrations.session_manager import Session
    s = Session(
        platform="instagram", username="x", cookies={"a": "b"},
        tokens={"t": "v"}, device_id="d1",
    )
    d = s.to_dict()
    s2 = Session.from_dict(d)
    assert s2.platform == "instagram"
    assert s2.cookies == {"a": "b"}
    assert s2.tokens == {"t": "v"}
    assert s2.device_id == "d1"


def test_session_store_save_and_get(tmpdir):
    from ugc_ai_overpower.integrations.session_manager import SessionStore, Session
    store = SessionStore(path=tmpdir)
    s = Session(platform="tiktok", username="alice", cookies={"k": "v"})
    store.save(s)
    loaded = store.get("tiktok", "alice")
    assert loaded is not None
    assert loaded.cookies == {"k": "v"}


def test_session_store_get_missing(tmpdir):
    from ugc_ai_overpower.integrations.session_manager import SessionStore
    store = SessionStore(path=tmpdir)
    assert store.get("tiktok", "missing") is None


def test_session_store_update(tmpdir):
    from ugc_ai_overpower.integrations.session_manager import SessionStore, Session
    store = SessionStore(path=tmpdir)
    s = Session(platform="instagram", username="bob", cookies={"v1": "1"})
    store.save(s)
    s.cookies = {"v1": "1", "v2": "2"}
    store.save(s)
    loaded = store.get("instagram", "bob")
    assert loaded is not None
    assert loaded.cookies == {"v1": "1", "v2": "2"}


def test_session_store_delete(tmpdir):
    from ugc_ai_overpower.integrations.session_manager import SessionStore, Session
    store = SessionStore(path=tmpdir)
    s = Session(platform="tiktok", username="alice")
    store.save(s)
    assert store.delete("tiktok", "alice") is True
    assert store.get("tiktok", "alice") is None
    assert store.delete("tiktok", "alice") is False


def test_session_store_list_all(tmpdir):
    from ugc_ai_overpower.integrations.session_manager import SessionStore, Session
    store = SessionStore(path=tmpdir)
    for i in range(3):
        store.save(Session(platform="tiktok", username=f"u{i}"))
    store.save(Session(platform="instagram", username="u0"))
    all_s = store.list_all()
    assert len(all_s) == 4
    assert len(store.list_all(platform="tiktok")) == 3
    assert len(store.list_all(platform="instagram")) == 1


def test_session_store_stats(tmpdir):
    from ugc_ai_overpower.integrations.session_manager import SessionStore, Session
    store = SessionStore(path=tmpdir)
    store.save(Session(platform="tiktok", username="a"))
    store.save(Session(platform="instagram", username="b"))
    stats = store.stats()
    assert stats["total"] == 2
    assert stats["by_platform"]["tiktok"] == 1
    assert stats["by_platform"]["instagram"] == 1


def test_session_store_cleanup_expired(tmpdir):
    from ugc_ai_overpower.integrations.session_manager import SessionStore, Session
    from datetime import datetime, timezone, timedelta
    store = SessionStore(path=tmpdir)
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    store.save(Session(platform="tiktok", username="expired", expires_at=past))
    store.save(Session(platform="tiktok", username="active", expires_at=future))
    n = store.cleanup_expired()
    assert n == 1
    assert store.get("tiktok", "active") is not None
    assert store.get("tiktok", "expired") is None


def test_session_manager_supported_platforms():
    from ugc_ai_overpower.integrations.session_manager import SessionManager
    sm = SessionManager()
    platforms = sm.SUPPORTED_PLATFORMS
    assert "tiktok" in platforms
    assert "instagram" in platforms
    assert "shopee" in platforms
    assert "tokopedia" in platforms


def test_session_manager_import_cookies(tmpdir):
    from ugc_ai_overpower.integrations.session_manager import SessionManager
    sm = SessionManager()
    s = sm.import_cookies(
        platform="tiktok", username="alice",
        cookies={"sessionid": "abc123"},
        user_agent="TestUA/1.0",
    )
    assert s.platform == "tiktok"
    assert s.cookies == {"sessionid": "abc123"}
    assert s.user_agent == "TestUA/1.0"
    assert sm.get("tiktok", "alice") is not None


def test_session_manager_revoke(tmpdir):
    from ugc_ai_overpower.integrations.session_manager import SessionManager, SessionStatus
    sm = SessionManager()
    sm.import_cookies("tiktok", "alice", cookies={"x": "y"})
    assert sm.revoke("tiktok", "alice") is True
    s = sm.get("tiktok", "alice")
    assert s is not None
    assert s.status == SessionStatus.REVOKED.value


def test_session_manager_health_check(tmpdir):
    from ugc_ai_overpower.integrations.session_manager import SessionManager
    sm = SessionManager()
    h = sm.health_check("tiktok", "missing")
    assert h["status"] == "missing"
    sm.import_cookies("tiktok", "alice", cookies={"x": "y"})
    h = sm.health_check("tiktok", "alice")
    assert h["status"] == "active"
    assert h["has_cookies"] is True


def test_session_manager_default_ua_for_tiktok():
    from ugc_ai_overpower.integrations.session_manager import SessionManager
    sm = SessionManager()
    s = sm.import_cookies("tiktok", "alice", cookies={"x": "y"})
    assert "musically" in s.user_agent.lower() or "tiktok" in s.user_agent.lower()


def test_session_manager_default_ua_for_instagram():
    from ugc_ai_overpower.integrations.session_manager import SessionManager
    sm = SessionManager()
    s = sm.import_cookies("instagram", "alice", cookies={"x": "y"})
    assert "Instagram" in s.user_agent


def test_social_module_imports():
    from ugc_ai_overpower.integrations.social_dispatch import (
        SocialDispatch, TikHubConfig, detect_platform, PLATFORMS_TIKHUB,
    )
    assert SocialDispatch is not None
    assert detect_platform is not None


def test_detect_platform_tiktok():
    from ugc_ai_overpower.integrations.social_dispatch import detect_platform
    url = "https://www.tiktok.com/@scout2015/video/6718335390845095173"
    assert detect_platform(url) == "tiktok"


def test_detect_platform_instagram_reel():
    from ugc_ai_overpower.integrations.social_dispatch import detect_platform
    url = "https://www.instagram.com/reel/CxYzAbC123/"
    assert detect_platform(url) == "instagram"


def test_detect_platform_youtube_shorts():
    from ugc_ai_overpower.integrations.social_dispatch import detect_platform
    url = "https://www.youtube.com/shorts/abc123XYZ"
    assert detect_platform(url) == "youtube"


def test_detect_platform_twitter_x():
    from ugc_ai_overpower.integrations.social_dispatch import detect_platform
    assert detect_platform("https://twitter.com/user/status/123456") == "twitter"
    assert detect_platform("https://x.com/user/status/123456") == "twitter"


def test_detect_platform_threads():
    from ugc_ai_overpower.integrations.social_dispatch import detect_platform
    url = "https://www.threads.net/@zuck/post/CxYzAbC"
    assert detect_platform(url) == "threads"


def test_detect_platform_unknown():
    from ugc_ai_overpower.integrations.social_dispatch import detect_platform
    assert detect_platform("https://example.com/some/random/path") is None


def test_detect_platform_empty():
    from ugc_ai_overpower.integrations.social_dispatch import detect_platform
    assert detect_platform("") is None


def test_social_dispatch_default_config():
    from ugc_ai_overpower.integrations.social_dispatch import SocialDispatch
    sd = SocialDispatch()
    assert sd.tiktokhub_config is not None
    assert sd.session_manager is not None


def test_social_dispatch_not_configured():
    from ugc_ai_overpower.integrations.social_dispatch import SocialDispatch, TikHubConfig
    sd = SocialDispatch(tiktokhub_config=TikHubConfig(api_key=""))
    assert sd.is_configured() is False


def test_social_dispatch_is_configured():
    from ugc_ai_overpower.integrations.social_dispatch import SocialDispatch, TikHubConfig
    sd = SocialDispatch(tiktokhub_config=TikHubConfig(api_key="test_key"))
    assert sd.is_configured() is True


def test_social_dispatch_supported_platforms():
    from ugc_ai_overpower.integrations.social_dispatch import SocialDispatch
    sd = SocialDispatch()
    p = sd.supported_platforms()
    assert "tiktok" in p
    assert "instagram" in p
    assert "shopee" in p
    assert "tokopedia" in p


def test_social_post_no_config():
    from ugc_ai_overpower.integrations.social_dispatch import SocialDispatch, TikHubConfig
    sd = SocialDispatch(tiktokhub_config=TikHubConfig(api_key=""))
    import asyncio
    result = asyncio.run(sd.post("tiktok", "alice", "hello"))
    assert result.status == "error"
    assert "TikHub not configured" in result.error


def test_social_post_no_session():
    from ugc_ai_overpower.integrations.social_dispatch import SocialDispatch, TikHubConfig
    sd = SocialDispatch(tiktokhub_config=TikHubConfig(api_key="key"))
    import asyncio
    result = asyncio.run(sd.post("tiktok", "missing", "hello"))
    assert result.status == "error"
    assert "No active session" in result.error


def test_social_post_unsupported_platform():
    from ugc_ai_overpower.integrations.social_dispatch import SocialDispatch, TikHubConfig
    sd = SocialDispatch(tiktokhub_config=TikHubConfig(api_key="key"))
    import asyncio
    result = asyncio.run(sd.post("unknownplatform", "alice", "hi"))
    assert result.status == "error"
    assert "Unsupported platform" in result.error


def test_social_engagement_unknown_url():
    from ugc_ai_overpower.integrations.social_dispatch import SocialDispatch
    sd = SocialDispatch()
    import asyncio
    m = asyncio.run(sd.get_engagement("https://example.com/foo"))
    assert m.views == 0


def test_ecom_module_imports():
    from ugc_ai_overpower.integrations.ecom_dispatch import (
        EcomConfig, EcomDispatch, AffiliateCache, CACHE_TTL_HOURS,
    )
    assert EcomDispatch is not None


def test_ecom_config_defaults():
    from ugc_ai_overpower.integrations.ecom_dispatch import EcomConfig
    cfg = EcomConfig()
    assert cfg.timeout_sec == 30


def test_ecom_dispatch_not_configured():
    from ugc_ai_overpower.integrations.ecom_dispatch import EcomDispatch, EcomConfig
    ed = EcomDispatch(config=EcomConfig())
    assert ed.is_configured("shopee") is False
    assert ed.is_configured("tiktokshop") is False
    assert ed.is_configured("lazada") is False
    assert ed.is_configured("tokopedia") is False


def test_ecom_dispatch_configured_platforms_empty():
    from ugc_ai_overpower.integrations.ecom_dispatch import EcomDispatch, EcomConfig
    ed = EcomDispatch(config=EcomConfig())
    assert ed.configured_platforms() == []


def test_ecom_dispatch_shopee_configured():
    from ugc_ai_overpower.integrations.ecom_dispatch import EcomDispatch, EcomConfig
    cfg = EcomConfig(shopee_affiliate_id="123", shopee_affiliate_token="abc")
    ed = EcomDispatch(config=cfg)
    assert ed.is_configured("shopee") is True
    assert "shopee" in ed.configured_platforms()


def test_ecom_dispatch_unsupported_platform():
    from ugc_ai_overpower.integrations.ecom_dispatch import EcomDispatch, EcomConfig
    ed = EcomDispatch(config=EcomConfig())
    assert ed.is_configured("unknown") is False


def test_ecom_get_link_unconfigured():
    from ugc_ai_overpower.integrations.ecom_dispatch import EcomDispatch, EcomConfig
    ed = EcomDispatch(config=EcomConfig())
    import asyncio
    link = asyncio.run(
        ed.get_affiliate_link("shopee", "999", "https://shopee.co.id/product/999")
    )
    assert link.error != ""
    assert "not configured" in link.error.lower()


def test_ecom_cache_get_missing(tmpdir):
    from ugc_ai_overpower.integrations.ecom_dispatch import AffiliateCache
    cache = AffiliateCache(path=tmpdir / "cache.db")
    assert cache.get("shopee", "missing") is None


def test_ecom_cache_put_and_get(tmpdir):
    from ugc_ai_overpower.integrations.ecom_dispatch import AffiliateCache, AffiliateLink
    cache = AffiliateCache(path=tmpdir / "cache.db")
    link = AffiliateLink(
        platform="shopee", product_id="123",
        original_url="https://shopee.co.id/p/123",
        affiliate_url="https://shope.ee/abc",
        commission_rate=0.05,
    )
    cache.put(link)
    loaded = cache.get("shopee", "123")
    assert loaded is not None
    assert loaded.affiliate_url == "https://shope.ee/abc"


def test_ecom_cache_expired(tmpdir):
    from ugc_ai_overpower.integrations.ecom_dispatch import AffiliateCache, AffiliateLink
    from datetime import datetime, timezone, timedelta
    cache = AffiliateCache(path=tmpdir / "cache.db")
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    link = AffiliateLink(
        platform="shopee", product_id="456",
        original_url="x", affiliate_url="y",
        expires_at=past,
    )
    cache.put(link)
    assert cache.get("shopee", "456") is None


def test_ecom_cache_stats(tmpdir):
    from ugc_ai_overpower.integrations.ecom_dispatch import AffiliateCache, AffiliateLink
    cache = AffiliateCache(path=tmpdir / "cache.db")
    cache.put(AffiliateLink(platform="shopee", product_id="1", original_url="x"))
    cache.put(AffiliateLink(platform="lazada", product_id="2", original_url="x"))
    s = cache.stats()
    assert s["total"] == 2
    assert s["platforms"] == 2


def test_ecom_cache_cleanup(tmpdir):
    from ugc_ai_overpower.integrations.ecom_dispatch import AffiliateCache, AffiliateLink
    from datetime import datetime, timezone, timedelta
    cache = AffiliateCache(path=tmpdir / "cache.db")
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    cache.put(AffiliateLink(platform="shopee", product_id="1", original_url="x", expires_at=past))
    n = cache.cleanup_expired()
    assert n == 1


def test_ecom_summary(tmpdir):
    from ugc_ai_overpower.integrations.ecom_dispatch import EcomDispatch, EcomConfig
    ed = EcomDispatch(config=EcomConfig())
    s = ed.summary()
    assert "configured_platforms" in s
    assert "config_status" in s
    assert s["config_status"]["shopee"] is False


def test_ecom_dispatch_summary_keys():
    from ugc_ai_overpower.integrations.ecom_dispatch import EcomDispatch, EcomConfig
    cfg = EcomConfig(shopee_affiliate_id="1", shopee_affiliate_token="2")
    ed = EcomDispatch(config=cfg)
    s = ed.summary()
    assert s["config_status"]["shopee"] is True
    assert s["config_status"]["lazada"] is False


def test_lazada_sign_deterministic():
    from ugc_ai_overpower.integrations.ecom_dispatch import EcomDispatch
    ed = EcomDispatch()
    params = {
        "app_key": "k1",
        "access_token": "t1",
        "timestamp": "12345",
        "format": "json",
        "v": "2.0",
    }
    s1 = ed._lazada_sign(params)
    s2 = ed._lazada_sign(params)
    assert s1 == s2
    assert len(s1) == 64


def test_lazada_sign_different_keys():
    from ugc_ai_overpower.integrations.ecom_dispatch import EcomDispatch, EcomConfig
    ed1 = EcomDispatch(config=EcomConfig(lazada_app_secret="secret_a"))
    ed2 = EcomDispatch(config=EcomConfig(lazada_app_secret="secret_b"))
    params = {"a": "1", "b": "2"}
    assert ed1._lazada_sign(params) != ed2._lazada_sign(params)


def test_character_module_imports():
    from ugc_ai_overpower.integrations.character_agent import (
        Character, CharacterAgent, ContentTone, ContentLanguage,
        NicheAdaptation, PersonalityTraits, PersonaIdentity,
        NICHE_PRESETS, PERSONA_TEMPLATES,
    )
    assert Character is not None
    assert NICHE_PRESETS is not None
    assert PERSONA_TEMPLATES is not None


def test_niche_presets_count():
    from ugc_ai_overpower.integrations.character_agent import NICHE_PRESETS
    assert len(NICHE_PRESETS) >= 5
    assert "beauty" in NICHE_PRESETS
    assert "tech" in NICHE_PRESETS
    assert "fashion" in NICHE_PRESETS


def test_persona_templates_count():
    from ugc_ai_overpower.integrations.character_agent import PERSONA_TEMPLATES
    assert len(PERSONA_TEMPLATES) >= 2


def test_niche_adaptation_fields():
    from ugc_ai_overpower.integrations.character_agent import NICHE_PRESETS
    for name, n in NICHE_PRESETS.items():
        assert n.niche == name
        assert isinstance(n.vocabulary, list)
        assert isinstance(n.forbidden_words, list)
        assert isinstance(n.references, list)
        assert isinstance(n.emoji_set, list)
        assert isinstance(n.hook_patterns, list)
        assert isinstance(n.cta_patterns, list)


def test_persona_identity_fingerprint_unique():
    from ugc_ai_overpower.integrations.character_agent import PersonaIdentity
    i1 = PersonaIdentity(name="A", age=25, gender="f", location="X", background="B")
    i2 = PersonaIdentity(name="B", age=25, gender="f", location="X", background="B")
    assert i1.fingerprint() != i2.fingerprint()


def test_persona_identity_fingerprint_same():
    from ugc_ai_overpower.integrations.character_agent import PersonaIdentity
    i1 = PersonaIdentity(name="A", age=25, gender="f", location="X", background="B")
    i2 = PersonaIdentity(name="A", age=25, gender="f", location="X", background="B")
    assert i1.fingerprint() == i2.fingerprint()


def test_character_create_persona():
    from ugc_ai_overpower.integrations.character_agent import CharacterAgent
    agent = CharacterAgent()
    char = agent.create_persona("Sari", "beauty")
    assert char.identity.name == "Sari"
    assert char.niche == "beauty"
    assert char.locked is True


def test_character_get():
    from ugc_ai_overpower.integrations.character_agent import CharacterAgent
    agent = CharacterAgent()
    agent.create_persona("Sari", "beauty")
    loaded = agent.get("sari_beauty")
    assert loaded is not None
    assert loaded.identity.name == "Sari"


def test_character_switch_niche_keeps_identity():
    from ugc_ai_overpower.integrations.character_agent import CharacterAgent
    agent = CharacterAgent()
    char1 = agent.create_persona("Sari", "beauty")
    char2 = agent.switch_niche("sari_beauty", "fashion")
    assert char2.identity.name == char1.identity.name
    assert char2.personality.tone == char1.personality.tone
    assert char2.niche == "fashion"
    assert char2.character_id == "sari_fashion"


def test_character_switch_niche_same_no_op():
    from ugc_ai_overpower.integrations.character_agent import CharacterAgent
    agent = CharacterAgent()
    agent.create_persona("Sari", "beauty")
    char2 = agent.switch_niche("sari_beauty", "beauty")
    assert char2.niche == "beauty"


def test_character_switch_niche_unknown_raises():
    from ugc_ai_overpower.integrations.character_agent import CharacterAgent
    agent = CharacterAgent()
    agent.create_persona("Sari", "beauty")
    with pytest.raises(ValueError, match="not found"):
        agent.switch_niche("sari_nonexistent", "tech")


def test_character_create_unknown_template_raises():
    from ugc_ai_overpower.integrations.character_agent import CharacterAgent
    agent = CharacterAgent()
    with pytest.raises(ValueError, match="Template .* not found"):
        agent.create_persona("NoOne", "beauty")


def test_character_create_unknown_niche_raises():
    from ugc_ai_overpower.integrations.character_agent import CharacterAgent
    agent = CharacterAgent()
    with pytest.raises(ValueError, match="not in presets"):
        agent.create_persona("Sari", "unknown_niche")


def test_character_get_voice():
    from ugc_ai_overpower.integrations.character_agent import CharacterAgent
    agent = CharacterAgent()
    char = agent.create_persona("Sari", "beauty")
    voice = agent.get_voice(char)
    assert voice["identity"]["name"] == "Sari"
    assert voice["niche"] == "beauty"
    assert "vocabulary" in voice
    assert "forbidden_words" in voice
    assert "emoji_set" in voice
    assert "hook_patterns" in voice


def test_character_voice_consistency_across_niches():
    from ugc_ai_overpower.integrations.character_agent import CharacterAgent
    agent = CharacterAgent()
    char_beauty = agent.create_persona("Rizky", "beauty")
    char_tech = agent.switch_niche("rizky_beauty", "tech")
    v1 = agent.get_voice(char_beauty)
    v2 = agent.get_voice(char_tech)
    assert v1["identity"] == v2["identity"]
    assert v1["tone"] == v2["tone"]
    assert v1["values"] == v2["values"]
    assert v1["vocabulary"] != v2["vocabulary"]


def test_character_generate_content_template():
    from ugc_ai_overpower.integrations.character_agent import CharacterAgent
    agent = CharacterAgent()
    char = agent.create_persona("Sari", "beauty")
    template = agent.generate_content_template(char, "lipstick review")
    assert template["character_id"] == "sari_beauty"
    assert template["niche"] == "beauty"
    assert "Sari" in template["body_outline"]
    assert "Jakarta" in template["body_outline"]


def test_character_add_niche():
    from ugc_ai_overpower.integrations.character_agent import CharacterAgent, NicheAdaptation
    agent = CharacterAgent()
    new_niche = NicheAdaptation(
        niche="automotive", vocabulary=["torque", "hp"],
        emoji_set=["🚗", "🏎️"],
    )
    agent.add_niche("automotive", new_niche)
    assert "automotive" in agent.list_niches()


def test_character_summary():
    from ugc_ai_overpower.integrations.character_agent import CharacterAgent
    agent = CharacterAgent()
    agent.create_persona("Sari", "beauty")
    s = agent.summary()
    assert s["total_characters"] == 1
    assert s["niches_available"]
    assert s["templates_available"] >= 2


def test_character_list_for_niche():
    from ugc_ai_overpower.integrations.character_agent import CharacterAgent
    agent = CharacterAgent()
    agent.create_persona("Sari", "beauty")
    agent.create_persona("Mbak Ani", "beauty")
    agent.create_persona("Rizky", "tech")
    beauty_chars = agent.list_for_niche("beauty")
    assert len(beauty_chars) == 2


def test_character_persistence():
    from ugc_ai_overpower.integrations.character_agent import CharacterAgent
    a1 = CharacterAgent()
    a1.create_persona("Sari", "beauty")
    a2 = CharacterAgent()
    loaded = a2.get("sari_beauty")
    assert loaded is not None
    assert loaded.identity.name == "Sari"


def test_character_to_from_dict():
    from ugc_ai_overpower.integrations.character_agent import (
        Character, CharacterAgent, PersonaIdentity, PersonalityTraits,
        NicheAdaptation, ContentTone,
    )
    agent = CharacterAgent()
    char = agent.create_persona("Sari", "beauty")
    d = char.to_dict()
    char2 = Character.from_dict(d)
    assert char2.identity.name == "Sari"
    assert char2.niche == "beauty"
    assert char2.personality.tone == ContentTone.WARM.value


def test_character_fingerprint_stable():
    from ugc_ai_overpower.integrations.character_agent import CharacterAgent
    agent = CharacterAgent()
    c1 = agent.create_persona("Sari", "beauty")
    c2 = agent.get("sari_beauty")
    assert c1.fingerprint() == c2.fingerprint()


def test_content_tone_enum_values():
    from ugc_ai_overpower.integrations.character_agent import ContentTone
    assert ContentTone.WARM.value == "warm"
    assert ContentTone.WITTY.value == "witty"
    assert ContentTone.PROFESSIONAL.value == "professional"


def test_content_language_enum():
    from ugc_ai_overpower.integrations.character_agent import ContentLanguage
    assert ContentLanguage.ID.value == "id"
    assert ContentLanguage.EN.value == "en"
    assert ContentLanguage.MIXED.value == "mixed"

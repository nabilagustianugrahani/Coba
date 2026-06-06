"""Tests for integrations/seo_optimizer.py — 30+ tests."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ugc_ai_overpower.integrations.seo_optimizer import (
    Keyword,
    SEOScore,
    SEOOptimizer,
    STOPWORDS,
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
def optimizer():
    return SEOOptimizer()


@pytest.fixture
def long_content():
    return (
        "Best Skincare Routine 2026: Complete Guide For Beginners\n\n"
        "Skincare is essential for healthy skin. A good skincare routine "
        "should include cleansing, toning, and moisturizing every day. "
        "In this guide we cover the best skincare products you can buy "
        "in 2026. Skincare does not need to be expensive, and the best "
        "skincare routine is the one you stick with. Many people make "
        "the mistake of buying too many skincare products at once. "
        "Start with a cleanser, then add a serum, and finish with "
        "moisturizer. Skincare brands are launching new items every "
        "year and the market is growing fast. Skincare is also a great "
        "gift for friends and family. This skincare guide will help "
        "you build a routine that works for your skin type and budget."
    )


# ---------- Keyword dataclass ----------

def test_keyword_to_dict_has_all_fields():
    k = Keyword(term="test")
    d = k.to_dict()
    for f in ("term", "search_volume", "competition", "cpc_usd", "trend", "intent"):
        assert f in d
    assert d["term"] == "test"


def test_keyword_default_values():
    k = Keyword(term="x")
    assert k.search_volume == 0
    assert k.competition == 0.0
    assert k.cpc_usd == 0.0
    assert k.trend == "stable"
    assert k.intent == "informational"


def test_keyword_custom_values():
    k = Keyword(term="x", search_volume=10, competition=0.5, cpc_usd=1.2,
                trend="rising", intent="transactional")
    d = k.to_dict()
    assert d["search_volume"] == 10
    assert d["competition"] == 0.5
    assert d["cpc_usd"] == 1.2
    assert d["trend"] == "rising"
    assert d["intent"] == "transactional"


# ---------- SEOScore dataclass ----------

def test_seoscore_to_dict_has_all_fields():
    s = SEOScore(overall=80.0, keyword_density=1.5, title_score=75.0,
                 meta_score=100.0, readability=85.0)
    d = s.to_dict()
    for f in ("overall", "keyword_density", "title_score", "meta_score",
              "readability", "suggestions"):
        assert f in d
    assert d["suggestions"] == []


def test_seoscore_default_suggestions_is_independent_per_instance():
    a = SEOScore(overall=0, keyword_density=0, title_score=0, meta_score=0, readability=0)
    b = SEOScore(overall=0, keyword_density=0, title_score=0, meta_score=0, readability=0)
    a.suggestions.append("x")
    assert b.suggestions == []  # default_factory list, no shared state


# ---------- _make_keyword ----------

def test_make_keyword_valid_trend_intent_ranges(optimizer):
    valid_intents = {"informational", "transactional", "navigational"}
    valid_trends = {"rising", "stable", "declining"}
    for term in ["alpha", "beta keyword", "gamma delta", "epsilon zeta eta"]:
        k = optimizer._make_keyword(term, "seed")
        assert k.trend in valid_trends
        assert k.intent in valid_intents
        assert 100 <= k.search_volume <= 50100
        assert 0.0 <= k.competition <= 1.0
        assert 0.0 <= k.cpc_usd <= 5.0


def test_make_keyword_deterministic(optimizer):
    k1 = optimizer._make_keyword("foo bar", "seed")
    k2 = optimizer._make_keyword("foo bar", "seed")
    assert k1 == k2


# ---------- research_keywords ----------

def test_research_keywords_returns_list_of_keyword(optimizer):
    results = _run(optimizer.research_keywords("skincare", "beauty", 10))
    assert isinstance(results, list)
    assert all(isinstance(r, Keyword) for r in results)
    assert len(results) == 10


def test_research_keywords_max_results_honored(optimizer):
    for n in (1, 3, 5, 20, 50):
        results = _run(optimizer.research_keywords("sneakers", "fashion", n))
        assert len(results) == n


def test_research_keywords_distinct_terms(optimizer):
    results = _run(optimizer.research_keywords("coffee", "drinks", 30))
    terms = [r.term for r in results]
    assert len(terms) == len(set(terms))


def test_research_keywords_deterministic_same_inputs(optimizer):
    a = _run(optimizer.research_keywords("dog food", "pets", 8))
    b = _run(optimizer.research_keywords("dog food", "pets", 8))
    assert [k.term for k in a] == [k.term for k in b]
    assert [k.search_volume for k in a] == [k.search_volume for k in b]


def test_research_keywords_cache_hits(optimizer):
    _run(optimizer.research_keywords("gaming", "tech", 5))
    assert f"gaming:tech:5" in optimizer._cache
    cached = optimizer._cache["gaming:tech:5"]
    fresh = _run(optimizer.research_keywords("gaming", "tech", 5))
    assert cached == fresh


def test_research_keywords_empty_seed_uses_niche(optimizer):
    # empty seed -> bases = [niche] only (split of '' -> [''] filtered out)
    results = _run(optimizer.research_keywords("", "fitness", 6))
    assert len(results) == 6
    for r in results:
        assert "fitness" in r.term


def test_research_keywords_single_word_seed(optimizer):
    results = _run(optimizer.research_keywords("yoga", "wellness", 4))
    assert all(isinstance(r.term, str) and r.term for r in results)


# ---------- score_content ----------

def test_score_content_empty(optimizer):
    s = optimizer.score_content("", "skincare")
    assert s.overall == 0.0
    assert s.keyword_density == 0.0
    assert "Content is empty" in s.suggestions


def test_score_content_short_text(optimizer):
    s = optimizer.score_content("Hi there", "skincare")
    assert 0.0 <= s.overall <= 100.0
    assert s.keyword_density == 0.0


def test_score_content_long_text(optimizer, long_content):
    s = optimizer.score_content(long_content, "skincare")
    assert 0.0 <= s.overall <= 100.0
    assert s.keyword_density > 0.0


def test_score_content_optimal_density(optimizer):
    # 100 tokens, 1 exact 'skincare' => density 1.0% (optimal range 0.5-2.5)
    tokens = ["skincare"] + ["filler"] * 99
    content = "Skincare " + " ".join(tokens)
    s = optimizer.score_content(content, "skincare")
    assert 0.5 <= s.keyword_density <= 2.5


def test_score_content_very_high_density(optimizer):
    tokens = ["skincare"] * 50 + ["x"] * 5
    content = " ".join(tokens)
    s = optimizer.score_content(content, "skincare")
    assert s.keyword_density > 2.5


def test_score_content_keyword_in_title_boosts_title_score(optimizer, long_content):
    with_kw = optimizer.score_content(long_content, "skincare")
    # Build a version with the keyword missing from the first line
    body_no_kw = "Different Title Here For A Long Line That Contains Nothing\n\n" + long_content.split("\n\n", 1)[1]
    without_kw = optimizer.score_content(body_no_kw, "skincare")
    assert with_kw.title_score >= without_kw.title_score


def test_score_content_overall_in_range(optimizer, long_content):
    s = optimizer.score_content(long_content, "skincare")
    for field in ("overall", "keyword_density", "title_score", "meta_score", "readability"):
        v = getattr(s, field)
        assert 0.0 <= v <= 100.0, f"{field} out of range: {v}"


# ---------- suggest_improvements ----------

def test_suggest_improvements_empty(optimizer):
    out = optimizer.suggest_improvements("", "skincare")
    assert "Add content" in out


def test_suggest_improvements_short_title(optimizer):
    content = "Short\n\n" + "word " * 200
    out = optimizer.suggest_improvements(content, "skincare")
    assert any("20-60" in s for s in out)


def test_suggest_improvements_long_title(optimizer):
    content = ("A" * 80) + "\n\n" + "word " * 200
    out = optimizer.suggest_improvements(content, "skincare")
    assert any("20-60" in s for s in out)


def test_suggest_improvements_missing_keyword_in_title(optimizer):
    content = "An Introduction To Something\n\n" + "word " * 200
    out = optimizer.suggest_improvements(content, "skincare")
    assert any("title" in s.lower() and "skincare" in s.lower() for s in out)


def test_suggest_improvements_low_density(optimizer):
    content = "Skincare Routine For You\n\n" + ("x " * 200)
    out = optimizer.suggest_improvements(content, "skincare")
    assert any("density" in s.lower() for s in out)


def test_suggest_improvements_high_density(optimizer):
    content = "Skincare " + ("skincare " * 30) + "\n\n" + "filler " * 5
    out = optimizer.suggest_improvements(content, "skincare")
    assert any("density" in s.lower() for s in out)


def test_suggest_improvements_short_content(optimizer):
    content = "Skincare guide\n\nThis is short."
    out = optimizer.suggest_improvements(content, "skincare")
    assert any("300" in s for s in out)


# ---------- generate_meta_description ----------

def test_meta_description_empty(optimizer):
    assert optimizer.generate_meta_description("") == ""


def test_meta_description_whitespace(optimizer):
    assert optimizer.generate_meta_description("   \n  ") == ""


def test_meta_description_truncates(optimizer):
    text = " ".join(["word"] * 100) + "."
    desc = optimizer.generate_meta_description(text, max_length=80)
    assert len(desc) <= 80


def test_meta_description_ends_with_ellipsis_when_truncated(optimizer):
    text = ("This is a fairly long sentence without any periods. " * 20).strip()
    desc = optimizer.generate_meta_description(text, max_length=50)
    assert desc.endswith("...")


def test_meta_description_multi_sentence(optimizer):
    text = "First sentence here. Second sentence follows. Third one too."
    desc = optimizer.generate_meta_description(text, max_length=160)
    # Should include at least the first sentence
    assert "First sentence" in desc


def test_meta_description_custom_max_length(optimizer):
    text = ("Sentence one. " * 5).strip()
    desc = optimizer.generate_meta_description(text, max_length=30)
    assert len(desc) <= 30


# ---------- generate_title_variants ----------

def test_title_variants_count(optimizer):
    variants = optimizer.generate_title_variants("any content", "skincare", 3)
    assert len(variants) == 3


def test_title_variants_count_larger(optimizer):
    variants = optimizer.generate_title_variants("any content", "skincare", 7)
    assert len(variants) == 7
    # No more than template pool
    assert len(variants) <= 7


def test_title_variants_contains_keyword(optimizer):
    variants = optimizer.generate_title_variants("any content", "skincare", 5)
    for v in variants:
        assert "skincare" in v.lower()


# ---------- extract_entities ----------

def test_extract_entities_capitalized_words(optimizer):
    content = "Alice went to Paris with Bob."
    out = optimizer.extract_entities(content)
    # First-word capitalized tokens at sentence start are still captured
    assert "Alice" in out
    assert "Paris" in out
    assert "Bob" in out


def test_extract_entities_quoted_phrases(optimizer):
    content = 'He said "machine learning" is fun. Also "data science".'
    out = optimizer.extract_entities(content)
    assert "machine learning" in out
    assert "data science" in out


def test_extract_entities_dedup(optimizer):
    content = "Alice Alice Alice. \"Alice\" Bob Bob."
    out = optimizer.extract_entities(content)
    assert out.count("Alice") == 1
    assert out.count("Bob") == 1


def test_extract_entities_empty(optimizer):
    assert optimizer.extract_entities("") == []


# ---------- internal_link_suggestions ----------

def test_internal_link_suggestions_match(optimizer):
    content = "Check our seo guide for tips."
    urls = ["https://example.com/seo-guide"]
    out = optimizer.internal_link_suggestions(content, urls)
    assert len(out) == 1
    assert "seo guide" in out[0]
    assert "https://example.com/seo-guide" in out[0]


def test_internal_link_suggestions_no_match(optimizer):
    content = "Nothing relevant here at all."
    urls = ["https://example.com/unrelated-page"]
    out = optimizer.internal_link_suggestions(content, urls)
    assert out == []


def test_internal_link_suggestions_empty_urls(optimizer):
    content = "Some content here."
    out = optimizer.internal_link_suggestions(content, [])
    assert out == []


def test_internal_link_suggestions_multiple_matches(optimizer):
    content = "Read our seo guide and our content strategy guide."
    urls = [
        "https://example.com/seo-guide",
        "https://example.com/content-strategy-guide",
        "https://example.com/unrelated",
    ]
    out = optimizer.internal_link_suggestions(content, urls)
    assert len(out) == 2
    assert any("seo guide" in s for s in out)
    assert any("content strategy guide" in s for s in out)


# ---------- Integration: research -> score -> suggest -> meta ----------

def test_full_seo_workflow(optimizer, long_content):
    # 1) Research
    keywords = _run(optimizer.research_keywords("skincare", "beauty", 5))
    assert len(keywords) > 0
    target = keywords[0].term.split()[-1]  # use last word of first term
    # 2) Score
    score = optimizer.score_content(long_content, target)
    assert isinstance(score, SEOScore)
    assert 0.0 <= score.overall <= 100.0
    # 3) Suggestions come back in the score
    assert isinstance(score.suggestions, list)
    # 4) Meta description is a string
    meta = optimizer.generate_meta_description(long_content, max_length=160)
    assert isinstance(meta, str) and len(meta) <= 160
    # 5) Title variants include the target
    variants = optimizer.generate_title_variants(long_content, target, 3)
    assert len(variants) == 3
    assert all(target.lower() in v.lower() for v in variants)

"""Tests for integrations/ab_testing.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ugc_ai_overpower.integrations.ab_testing import (
    ABTest,
    ABTestResult,
    ABTesting,
    Variant,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ab():
    return ABTesting()


@pytest.fixture
def two_variants():
    return [
        Variant(id="v1", content="A", caption="cap1", hashtags=["x"]),
        Variant(id="v2", content="B", caption="cap2", hashtags=["y"]),
    ]


# ---------------------------------------------------------------------------
# Variant
# ---------------------------------------------------------------------------

def test_variant_engagement_rate_zero_impressions():
    v = Variant(id="v1", content="A")
    assert v.engagement_rate() == 0.0


def test_variant_engagement_rate_normal():
    v = Variant(id="v1", content="A", impressions=100, engagements=25)
    assert v.engagement_rate() == 0.25


def test_variant_conversion_rate_zero_impressions():
    v = Variant(id="v1", content="A")
    assert v.conversion_rate() == 0.0


def test_variant_conversion_rate_normal():
    v = Variant(id="v1", content="A", impressions=200, conversions=10)
    assert v.conversion_rate() == 0.05


def test_variant_to_dict():
    v = Variant(id="v1", content="A", image_url="i.png", caption="c",
                hashtags=["a", "b"], impressions=5, engagements=2, conversions=1)
    d = v.to_dict()
    assert d["id"] == "v1"
    assert d["content"] == "A"
    assert d["image_url"] == "i.png"
    assert d["caption"] == "c"
    assert d["hashtags"] == ["a", "b"]
    assert d["impressions"] == 5
    assert d["engagements"] == 2
    assert d["conversions"] == 1


# ---------------------------------------------------------------------------
# ABTestResult
# ---------------------------------------------------------------------------

def test_abtestresult_to_dict():
    r = ABTestResult(winner_id="v1", winner_rate=0.1, loser_id="v2",
                     loser_rate=0.05, uplift_percent=100.0, confidence=0.95,
                     sample_size=1000, is_significant=True)
    d = r.to_dict()
    assert d == {
        "winner_id": "v1", "winner_rate": 0.1, "loser_id": "v2",
        "loser_rate": 0.05, "uplift_percent": 100.0, "confidence": 0.95,
        "sample_size": 1000, "is_significant": True,
    }


def test_abtestresult_default_construction():
    r = ABTestResult(winner_id="v1", winner_rate=0.0, loser_id="v2",
                     loser_rate=0.0, uplift_percent=0.0, confidence=0.0,
                     sample_size=0, is_significant=False)
    assert r.is_significant is False
    assert r.sample_size == 0


# ---------------------------------------------------------------------------
# ABTest
# ---------------------------------------------------------------------------

def test_abtest_to_dict():
    t = ABTest(id="t1", name="n", variants=[Variant(id="v1", content="A")],
               traffic_split=[1.0], created_at="2026-01-01T00:00:00Z")
    d = t.to_dict()
    assert d["id"] == "t1"
    assert d["name"] == "n"
    assert len(d["variants"]) == 1
    assert d["traffic_split"] == [1.0]


# ---------------------------------------------------------------------------
# create_test
# ---------------------------------------------------------------------------

def test_create_test_empty_variants_raises(ab):
    with pytest.raises(ValueError, match="variants must not be empty"):
        ab.create_test("t", [])


def test_create_test_mismatched_split_raises(ab, two_variants):
    with pytest.raises(ValueError, match="traffic_split length must match variants"):
        ab.create_test("t", two_variants, traffic_split=[1.0])


def test_create_test_split_sum_not_one_raises(ab, two_variants):
    with pytest.raises(ValueError, match="traffic_split must sum to 1.0"):
        ab.create_test("t", two_variants, traffic_split=[0.3, 0.3])


def test_create_test_default_split(ab, two_variants):
    tid = ab.create_test("t", two_variants)
    t = ab.get_test(tid)
    assert len(t.traffic_split) == 2
    assert all(abs(w - 0.5) < 1e-6 for w in t.traffic_split)


def test_create_test_custom_split(ab, two_variants):
    tid = ab.create_test("t", two_variants, traffic_split=[0.7, 0.3])
    t = ab.get_test(tid)
    assert t.traffic_split == [0.7, 0.3]


def test_create_test_returns_unique_ids(ab, two_variants):
    id1 = ab.create_test("a", two_variants)
    id2 = ab.create_test("b", two_variants)
    assert id1 != id2
    assert id1.startswith("test_")


def test_create_test_three_way_default_split(ab):
    vs = [Variant(id=f"v{i}", content=str(i)) for i in range(3)]
    tid = ab.create_test("t", vs)
    t = ab.get_test(tid)
    assert all(abs(w - 1 / 3) < 1e-6 for w in t.traffic_split)


# ---------------------------------------------------------------------------
# assign_variant
# ---------------------------------------------------------------------------

def test_assign_variant_unknown_test_raises(ab):
    with pytest.raises(KeyError):
        ab.assign_variant("nope", "user1")


def test_assign_variant_deterministic(ab, two_variants):
    tid = ab.create_test("t", two_variants)
    v1 = ab.assign_variant(tid, "user_42")
    v2 = ab.assign_variant(tid, "user_42")
    assert v1.id == v2.id


def test_assign_variant_distributes_users(ab, two_variants):
    tid = ab.create_test("t", two_variants, traffic_split=[0.5, 0.5])
    counts = {"v1": 0, "v2": 0}
    for i in range(1000):
        v = ab.assign_variant(tid, f"user_{i}")
        counts[v.id] += 1
    assert counts["v1"] > 300
    assert counts["v2"] > 300


def test_assign_variant_custom_split_70_30(ab, two_variants):
    tid = ab.create_test("t", two_variants, traffic_split=[0.7, 0.3])
    counts = {"v1": 0, "v2": 0}
    for i in range(2000):
        v = ab.assign_variant(tid, f"user_{i}")
        counts[v.id] += 1
    assert counts["v1"] > counts["v2"]
    assert 0.6 < counts["v1"] / 2000 < 0.8


# ---------------------------------------------------------------------------
# record_*
# ---------------------------------------------------------------------------

def test_record_impression_increments(ab, two_variants):
    tid = ab.create_test("t", two_variants)
    ab.record_impression(tid, "v1")
    ab.record_impression(tid, "v1")
    ab.record_impression(tid, "v2")
    t = ab.get_test(tid)
    v1 = next(v for v in t.variants if v.id == "v1")
    v2 = next(v for v in t.variants if v.id == "v2")
    assert v1.impressions == 2
    assert v2.impressions == 1


def test_record_engagement_increments(ab, two_variants):
    tid = ab.create_test("t", two_variants)
    ab.record_engagement(tid, "v1")
    v1 = next(v for v in ab.get_test(tid).variants if v.id == "v1")
    assert v1.engagements == 1


def test_record_conversion_increments(ab, two_variants):
    tid = ab.create_test("t", two_variants)
    ab.record_conversion(tid, "v1")
    v1 = next(v for v in ab.get_test(tid).variants if v.id == "v1")
    assert v1.conversions == 1


def test_record_impression_unknown_test_raises(ab):
    with pytest.raises(KeyError):
        ab.record_impression("nope", "v1")


def test_record_impression_unknown_variant_raises(ab, two_variants):
    tid = ab.create_test("t", two_variants)
    with pytest.raises(KeyError):
        ab.record_impression(tid, "v_ghost")


def test_record_engagement_unknown_test_raises(ab):
    with pytest.raises(KeyError):
        ab.record_engagement("nope", "v1")


def test_record_conversion_unknown_test_raises(ab):
    with pytest.raises(KeyError):
        ab.record_conversion("nope", "v1")


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------

def test_analyze_unknown_test_raises(ab):
    with pytest.raises(KeyError):
        ab.analyze("nope")


def test_analyze_less_than_two_variants_raises(ab):
    from ugc_ai_overpower.integrations.ab_testing import ABTesting as _A
    ab2 = _A()
    tid = ab2.create_test("t", [Variant(id="v1", content="A")])
    with pytest.raises(ValueError, match="Need at least 2 variants"):
        ab2.analyze(tid)


def test_analyze_no_data(ab, two_variants):
    tid = ab.create_test("t", two_variants)
    r = ab.analyze(tid)
    assert r.winner_rate == 0.0
    assert r.loser_rate == 0.0
    assert r.sample_size == 0
    assert r.is_significant is False
    assert 0.0 <= r.confidence <= 1.0


def test_analyze_clear_winner_insufficient_sample(ab, two_variants):
    tid = ab.create_test("t", two_variants)
    for _ in range(20):
        ab.record_impression(tid, "v1")
        ab.record_conversion(tid, "v1")
    for _ in range(20):
        ab.record_impression(tid, "v2")
    r = ab.analyze(tid, min_samples=100)
    assert r.winner_id == "v1"
    assert r.is_significant is False
    assert r.sample_size == 40


def test_analyze_clear_winner_sufficient_sample(ab, two_variants):
    tid = ab.create_test("t", two_variants)
    for _ in range(1000):
        ab.record_impression(tid, "v1")
        ab.record_conversion(tid, "v1")
    for _ in range(1000):
        ab.record_impression(tid, "v2")
        if _ % 5 == 0:
            ab.record_conversion(tid, "v2")
    r = ab.analyze(tid, min_samples=100)
    assert r.winner_id == "v1"
    assert r.is_significant is True
    assert r.confidence > 0.95
    assert r.uplift_percent > 0


def test_analyze_confidence_in_range(ab, two_variants):
    tid = ab.create_test("t", two_variants)
    for _ in range(500):
        ab.record_impression(tid, "v1")
        if _ % 10 == 0:
            ab.record_conversion(tid, "v1")
    for _ in range(500):
        ab.record_impression(tid, "v2")
        if _ % 20 == 0:
            ab.record_conversion(tid, "v2")
    r = ab.analyze(tid)
    assert 0.0 <= r.confidence <= 1.0


def test_analyze_ties(ab, two_variants):
    tid = ab.create_test("t", two_variants)
    for _ in range(100):
        ab.record_impression(tid, "v1")
        ab.record_conversion(tid, "v1")
    for _ in range(100):
        ab.record_impression(tid, "v2")
        ab.record_conversion(tid, "v2")
    r = ab.analyze(tid)
    assert r.winner_rate == r.loser_rate
    assert r.uplift_percent == 0.0
    assert r.is_significant is False


def test_analyze_three_variants_picks_top(ab):
    vs = [Variant(id=f"v{i}", content=str(i)) for i in range(3)]
    ab3 = ABTesting()
    tid = ab3.create_test("t", vs, traffic_split=[0.34, 0.33, 0.33])
    for v_id, conv_rate in [("v0", 0.05), ("v1", 0.20), ("v2", 0.10)]:
        for _ in range(500):
            ab3.record_impression(tid, v_id)
            if _ < int(500 * conv_rate):
                ab3.record_conversion(tid, v_id)
    r = ab3.analyze(tid, min_samples=100)
    assert r.winner_id == "v1"


# ---------------------------------------------------------------------------
# multi_variate_score
# ---------------------------------------------------------------------------

def test_multi_variate_score_unknown_test_raises(ab):
    with pytest.raises(KeyError):
        ab.multi_variate_score("nope")


def test_multi_variate_score_all_variants_present(ab, two_variants):
    tid = ab.create_test("t", two_variants)
    scores = ab.multi_variate_score(tid)
    assert set(scores.keys()) == {"v1", "v2"}


def test_multi_variate_score_values_in_unit_interval(ab, two_variants):
    tid = ab.create_test("t", two_variants)
    for _ in range(100):
        ab.record_impression(tid, "v1")
        ab.record_engagement(tid, "v1")
        if _ % 10 == 0:
            ab.record_conversion(tid, "v1")
    for _ in range(100):
        ab.record_impression(tid, "v2")
        if _ % 5 == 0:
            ab.record_engagement(tid, "v2")
    scores = ab.multi_variate_score(tid)
    for s in scores.values():
        assert 0.0 <= s <= 1.0


def test_multi_variate_score_zero_data(ab, two_variants):
    tid = ab.create_test("t", two_variants)
    scores = ab.multi_variate_score(tid)
    assert scores == {"v1": 0.0, "v2": 0.0}


# ---------------------------------------------------------------------------
# z_test edge cases
# ---------------------------------------------------------------------------

def test_z_test_zero_pool_returns_one():
    assert ABTesting._z_test_proportions(0.0, 100, 0.0, 100) == 1.0


def test_z_test_pool_one_returns_one():
    assert ABTesting._z_test_proportions(1.0, 100, 1.0, 100) == 1.0


def test_z_test_zero_n_returns_one():
    assert ABTesting._z_test_proportions(0.1, 0, 0.2, 100) == 1.0


def test_z_test_normal_case_in_range():
    p = ABTesting._z_test_proportions(0.10, 1000, 0.05, 1000)
    assert 0.0 <= p <= 1.0
    assert p < 0.05


def test_z_test_symmetric():
    p1 = ABTesting._z_test_proportions(0.10, 500, 0.05, 500)
    p2 = ABTesting._z_test_proportions(0.05, 500, 0.10, 500)
    assert abs(p1 - p2) < 1e-9


def test_z_test_identical_proportions_high_p():
    p = ABTesting._z_test_proportions(0.05, 1000, 0.05, 1000)
    assert p > 0.5


# ---------------------------------------------------------------------------
# Integration: full create -> assign -> record -> analyze
# ---------------------------------------------------------------------------

def test_integration_full_flow(ab, two_variants):
    tid = ab.create_test("cta_test", two_variants, traffic_split=[0.5, 0.5])
    for i in range(500):
        uid = f"user_{i}"
        v = ab.assign_variant(tid, uid)
        ab.record_impression(tid, v.id)
        if i % 4 == 0:
            ab.record_engagement(tid, v.id)
        if i % 20 == 0 and v.id == "v1":
            ab.record_conversion(tid, v.id)
        if i % 40 == 0 and v.id == "v2":
            ab.record_conversion(tid, v.id)
    r = ab.analyze(tid, min_samples=100)
    assert r.sample_size > 0
    assert r.winner_id in {"v1", "v2"}
    assert 0.0 <= r.confidence <= 1.0


def test_integration_list_tests(ab, two_variants):
    assert ab.list_tests() == []
    id1 = ab.create_test("a", two_variants)
    id2 = ab.create_test("b", two_variants)
    listed = ab.list_tests()
    assert {t.id for t in listed} == {id1, id2}
